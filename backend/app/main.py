# backend/app/main.py - 修改后的完整文件

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import asyncio
from dotenv import load_dotenv
from app.core.game_state import GameStateMachine, GamePhase, Role
from pydantic import BaseModel
import random
from app.services.llm_service import get_ai_response_with_timeout
from app.services.memory_service import memory_db
ai_thoughts = {} 

class VoteRequest(BaseModel):
    voter_id: int
    target_id: int

class AISpeakRequest(BaseModel):
    player_id: int
    speech: str
    thought: str = ""

load_dotenv()

game = GameStateMachine()
human_player_id = 1  # 人类玩家固定为1号
human_night_action = {}  # 存储人类玩家的夜晚行动
human_night_action_received = asyncio.Event()  # 等待人类玩家行动的事件
connections = {}  # 存储所有WebSocket连接
ai_thoughts = {}
current_timeout_task = None

async def broadcast(message):
    """广播消息给所有连接的客户端"""
    dead = []
    for pid, conn in connections.items():
        try:
            await conn.send_text(json.dumps(message))
            print(f"广播给 {pid}: {message.get('type')}")
        except:
            dead.append(pid)
    for pid in dead:
        connections.pop(pid, None)

async def human_timeout_task(player_id: int, speech_timeout: int = 60):
    """人类玩家发言超时处理"""
    global current_timeout_task
    await asyncio.sleep(speech_timeout)
    
    if game.current_speaker == player_id and game.phase == GamePhase.DAY_DISCUSSION:
        print(f"人类玩家 {player_id} 超时")
        
        await broadcast({
            "type": "TIMEOUT",
            "data": {"player_id": player_id, "content": "发言超时，自动跳过"}
        })
        
        # 自动跳过，进入下一个
        next_speaker = game.next_speaker()
        if next_speaker:
            if next_speaker == human_player_id:
                await broadcast({
                    "type": "YOUR_TURN",
                    "data": {"current": game.current_speaker}
                })
                current_timeout_task = asyncio.create_task(human_timeout_task(human_player_id, 60))
            else:
                await broadcast({
                    "type": "NEXT_SPEAKER",
                    "data": {"current": next_speaker}
                })
                asyncio.create_task(handle_ai_turn(next_speaker))
        else:
            # 发言结束，进入投票
            game.phase = GamePhase.DAY_VOTE
            await broadcast({
                "type": "VOTE_PHASE",
                "data": {"content": "发言结束，请投票"}
            })
            await auto_ai_votes()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("服务器启动")
    yield
    print("服务器关闭")

app = FastAPI(title="Werewolf AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.get("/api/game/status")
async def game_status():
    return {
        "phase": game.phase.value if hasattr(game.phase, 'value') else str(game.phase),
        "alive_players": game.alive_players,
        "current_speaker": game.current_speaker,
        "round": game.round,
    }

@app.get("/api/game/trust-matrix")
async def get_trust_matrix():
    """获取信任矩阵（从Redis读取真实数据）"""
    try:
        if memory_db:
            matrix = memory_db.get_trust_matrix()
            print(f"[DEBUG] 信任矩阵数据: {matrix}")  # 添加调试
            return {"trust_matrix": matrix}
        else:
            matrix = {str(i): {str(j): 50 for j in range(1, 7)} for i in range(1, 7)}
            return {"trust_matrix": matrix}
    except Exception as e:
        print(f"获取信任矩阵失败: {e}")
        matrix = {str(i): {str(j): 50 for j in range(1, 7)} for i in range(1, 7)}
        return {"trust_matrix": matrix}

@app.get("/api/ai/thought/{player_id}")
async def get_ai_thought(player_id: int):
    """获取AI的内心独白"""
    thought = ai_thoughts.get(player_id, "暂无内心独白")
    return {"thought": thought}

@app.post("/api/game/start")
async def start_game():
    global game, current_timeout_task, ai_thoughts, human_night_action, human_night_action_received
    
    # 重置游戏状态
    game = GameStateMachine()
    ai_thoughts = {}
    human_night_action = {}
    human_night_action_received.clear()
    
    # 清空记忆
    try:
        if memory_db and memory_db.redis_available:
            memory_db.redis.delete(memory_db.HISTORY_KEY)
            memory_db.redis.delete(memory_db.SUMMARY_KEY)
            memory_db.redis.delete(memory_db.TRUST_KEY)
            memory_db.redis.delete(memory_db.VOTE_KEY)
        elif memory_db:
            memory_db._memory_history = []
            memory_db._memory_summary = ""
            memory_db._memory_trust = {}
            memory_db._memory_votes = []
    except Exception as e:
        print(f"清空记忆失败: {e}")
    
    player_ids = [1, 2, 3, 4, 5, 6]
    roles = game.assign_roles(player_ids)
    
    werewolves = [pid for pid, role in roles.items() if role == Role.WEREWOLF]
    print(f"狼人队伍: {werewolves}")
    print(f"角色分配: {roles}")

    # 发送角色给每个玩家
    for player_id, conn in connections.items():
        if player_id in roles:
            role_value = roles[player_id].value if hasattr(roles[player_id], 'value') else str(roles[player_id])
            
            message_data = {
                "type": "ROLE_ASSIGNMENT",
                "data": {
                    "player_id": player_id,
                    "role": role_value,
                    "player_number": player_id
                }
            }
            
            if roles[player_id] == Role.WEREWOLF:
                teammates = [pid for pid in werewolves if pid != player_id]
                message_data["data"]["werewolf_teammates"] = teammates
            
            await conn.send_text(json.dumps(message_data))
            print(f"发送角色给玩家 {player_id}: {role_value}")

    # 先进入第一夜
    await start_first_night()

    return {"status": "ok"}

async def start_first_night():
    """第一夜开始"""
    global game
    
    print("\n[第一夜] 游戏开始，进入第一夜...")
    
    await broadcast({
        "type": "NIGHT_START",
        "data": {"content": "游戏开始，第一夜降临..."}
    })
    
    # 1. 狼人杀人
    game.phase = GamePhase.NIGHT_WOLF
    await handle_wolf_action()
    
    # 2. 预言家查验
    game.phase = GamePhase.NIGHT_SEER
    await handle_seer_action()
    
    # 3. 女巫行动（第一夜）
    game.phase = GamePhase.NIGHT_WITCH
    await handle_witch_action()
    
    # 4. 解决夜晚结果
    deaths = game.resolve_night()
    
    # 广播夜晚结果
    if deaths:
        for died in deaths:
            await broadcast({
                "type": "NIGHT_RESULT",
                "data": {
                    "player_id": died,
                    "content": f"天亮了，P{died} 在夜晚死亡"
                }
            })
    else:
        await broadcast({
            "type": "NIGHT_RESULT",
            "data": {
                "player_id": None,
                "content": "天亮了，昨晚是个平安夜"
            }
        })
    
    # 开始第一天白天
    await start_day_phase()

async def handle_wolf_action():
    """处理狼人行动，支持人类玩家主动选择"""
    wolves = [p for p in game.players if p["role"] == Role.WEREWOLF and p["alive"]]
    
    if not wolves:
        return
    
    # 检查人类玩家是否是狼人
    human_is_wolf = human_player_id in [w["id"] for w in wolves]
    
    if human_is_wolf:
        # 人类玩家是狼人，需要等待人类选择
        alive_non_wolves = [p["id"] for p in game.players if p["alive"] and p["role"] != Role.WEREWOLF]
        
        await broadcast({
            "type": "NIGHT_CHOOSE_TARGET",
            "data": {
                "action": "wolf_kill",
                "candidates": alive_non_wolves,
                "content": "你是狼人，请选择要击杀的目标"
            }
        })
        
        # 等待人类玩家选择（30秒超时）
        try:
            await asyncio.wait_for(human_night_action_received.wait(), timeout=30)
            target = human_night_action.get("wolf_kill")
            human_night_action_received.clear()
            
            if target and target in alive_non_wolves:
                for wolf in wolves:
                    game.record_wolf_vote(wolf["id"], target)
                print(f"[狼人] 人类玩家选择了击杀 {target}")
                await broadcast({
                    "type": "NIGHT_ACTION",
                    "data": {"content": f"狼人选择了击杀 P{target}"}
                })
                return
        except asyncio.TimeoutError:
            print("[狼人] 人类玩家超时，随机选择")
    
    # AI狼人或人类超时，自动选择
    alive_non_wolves = [p["id"] for p in game.players if p["alive"] and p["role"] != Role.WEREWOLF]
    if alive_non_wolves:
        target = random.choice(alive_non_wolves)
        for wolf in wolves:
            game.record_wolf_vote(wolf["id"], target)
        print(f"[狼人] AI选择了击杀 {target}")
        await broadcast({
            "type": "NIGHT_ACTION",
            "data": {"content": f"狼人选择了目标..."}
        })


async def handle_seer_action():
    """处理预言家行动，支持人类玩家主动选择"""
    seers = [p for p in game.players if p["role"] == Role.SEER and p["alive"]]
    
    if not seers:
        return
    
    # 检查人类玩家是否是预言家
    human_is_seer = human_player_id in [s["id"] for s in seers]
    
    if human_is_seer:
        alive_players = [p["id"] for p in game.players if p["alive"] and p["id"] != human_player_id]
        
        await broadcast({
            "type": "NIGHT_CHOOSE_TARGET",
            "data": {
                "action": "seer_check",
                "candidates": alive_players,
                "content": "你是预言家，请选择要查验的目标"
            }
        })
        
        try:
            await asyncio.wait_for(human_night_action_received.wait(), timeout=30)
            target = human_night_action.get("seer_check")
            human_night_action_received.clear()
            
            if target and target in alive_players:
                game.record_seer_check(target)
                result = game.get_seer_result()
                is_wolf = (result == Role.WEREWOLF)
                
                # 私聊发送查验结果给预言家
                if human_player_id in connections:
                    await connections[human_player_id].send_text(json.dumps({
                        "type": "SEER_RESULT",
                        "data": {
                            "target": target,
                            "result": "狼人" if is_wolf else "好人"
                        }
                    }))
                
                print(f"[预言家] 人类玩家查验了 {target}")
                return
        except asyncio.TimeoutError:
            print("[预言家] 人类玩家超时，随机选择")
    
    # AI预言家或人类超时，自动选择
    alive_players = [p["id"] for p in game.players if p["alive"] and p["id"] != seers[0]["id"]]
    if alive_players:
        target = random.choice(alive_players)
        game.record_seer_check(target)
        result = game.get_seer_result()
        is_wolf = (result == Role.WEREWOLF)
        print(f"[预言家] AI查验了 {target}, 结果是{'狼人' if is_wolf else '好人'}")

async def handle_witch_action():
    """处理女巫行动，支持人类玩家主动选择"""
    witches = [p for p in game.players if p["role"] == Role.WITCH and p["alive"]]
    
    if not witches:
        return
    
    # 检查人类玩家是否是女巫
    human_is_witch = human_player_id in [w["id"] for w in witches]
    
    # 获取被杀目标
    killed_target = game.killed_target
    
    if human_is_witch:
        alive_players = [p["id"] for p in game.players if p["alive"] and p["id"] != human_player_id]
        
        await broadcast({
            "type": "NIGHT_CHOOSE_TARGET",
            "data": {
                "action": "witch_action",
                "candidates": {
                    "killed_target": game.killed_target,
                    "candidates": alive_players,
                    "message": f"被杀的是 P{game.killed_target}，是否使用解药？"
                }
            }
        })
        
        # 等待人类玩家选择（30秒超时）
        try:
            await asyncio.wait_for(human_night_action_received.wait(), timeout=30)
            save_target = human_night_action.get("witch_save")
            poison_target = human_night_action.get("witch_poison")
            human_night_action_received.clear()
            
            # 记录女巫行动
            game.record_witch_action(save_target=save_target, poison_target=poison_target)
            
            if save_target:
                print(f"[女巫] 人类玩家救了 {save_target}")
            if poison_target:
                print(f"[女巫] 人类玩家毒死了 {poison_target}")
            return
        except asyncio.TimeoutError:
            print("[女巫] 人类玩家超时，自动行动")
    
    # AI女巫或人类超时，自动行动
    await auto_witch_action()

async def handle_ai_turn(player_id: int):
    """AI发言 - 使用真正的LLM"""
    print(f"AI {player_id} 开始发言")
    
    # 获取玩家角色
    player_role = None
    for p in game.players:
        if p["id"] == player_id:
            player_role = p["role"]
            break
    
    if not player_role:
        await handle_ai_turn_fallback(player_id)
        return
    
    # 构建游戏状态描述
    game_state_text = f"""
当前是第{game.round}天，白天讨论阶段。
存活玩家: {game.alive_players}
你是{player_id}号玩家，你的身份是{player_role.value}。
"""
    
    # 获取对话历史
    history = memory_db.get_full_context_for_ai() if memory_db else ""
    
    try:
        # 调用LLM获取AI回复
        response = await get_ai_response_with_timeout(
            player_id=player_id,
            role=player_role.value,
            game_state=game_state_text,
            history=history,
            timeout=15
        )
        
        speech = response.get("speech", "我是好人，过")
        thought = response.get("thought", "我在思考...")
        
        # ===== 保存内心独白 =====
        ai_thoughts[player_id] = thought
        print(f"💭 AI {player_id} 内心独白: {thought}")
        
        # 保存到memory
        if memory_db:
            memory_db.save_message(player_id, player_role.value, speech, response.get("trust_scores"))
        
        # 执行发言
        await ai_speak_internal(player_id, speech, thought)
        
    except Exception as e:
        print(f"AI调用失败: {e}，使用降级发言")
        await handle_ai_turn_fallback(player_id)


async def handle_ai_turn_fallback(player_id: int):
    """降级发言（API失败时使用）"""
    await asyncio.sleep(1)
    
    speeches = [
        f"我是{player_id}号，我觉得需要更多信息才能判断。",
        f"大家好，我是{player_id}号，目前还没有明确目标。",
        f"{player_id}号玩家发言，我会仔细观察每个人的表现。",
        f"我认为现在下结论还太早，我是{player_id}号。",
        f"我是{player_id}号，先听听别人怎么说。"
    ]
    
    thoughts = [
        f"我是AI玩家{player_id}，我在分析当前局势...",
        f"我在考虑谁更可能是狼人...",
        f"我需要更多发言才能做出判断。",
        f"我在观察每个人的行为模式。",
        f"当前的投票情况对我来说还不够明确。"
    ]
    
    speech = random.choice(speeches)
    thought = random.choice(thoughts)
    
    # ===== 保存内心独白 =====
    ai_thoughts[player_id] = thought
    print(f"💭 AI {player_id} 内心独白(降级): {thought}")
    
    await ai_speak_internal(player_id, speech, thought)
    await ai_speak_internal(player_id, random.choice(speeches), thought)

async def ai_speak_internal(player_id: int, speech: str, thought: str):
    """内部AI发言函数，避免HTTP调用"""
    global current_timeout_task
    
    # 保存内心独白
    ai_thoughts[player_id] = thought
    
    # 广播发言
    await broadcast({
        "type": "SPEECH",
        "data": {
            "player_id": player_id,
            "content": speech
        }
    })
    
    print(f"AI {player_id} 发言: {speech}")
    
    # 检查是否是当前发言者
    if game.phase == GamePhase.DAY_DISCUSSION and game.current_speaker == player_id:
        print(f"AI {player_id} 发言完成，切换到下一个")
        
        # 切换到下一个发言者
        next_speaker = game.next_speaker()
        
        if next_speaker is not None:
            print(f"下一个发言者: {next_speaker}")
            
            if next_speaker == human_player_id:
                # 轮到人类玩家
                await broadcast({
                    "type": "YOUR_TURN",
                    "data": {"current": game.current_speaker}
                })
                if current_timeout_task:
                    current_timeout_task.cancel()
                current_timeout_task = asyncio.create_task(human_timeout_task(human_player_id, 60))
            else:
                # 轮到AI
                await broadcast({
                    "type": "NEXT_SPEAKER",
                    "data": {"current": next_speaker}
                })
                # 异步调用下一个AI
                asyncio.create_task(handle_ai_turn(next_speaker))
        else:
            # 发言结束，进入投票
            print("所有玩家发言完毕，进入投票阶段")
            game.phase = GamePhase.DAY_VOTE
            await broadcast({
                "type": "VOTE_PHASE",
                "data": {"content": "发言结束，请投票"}
            })
            await auto_ai_votes()

@app.post("/api/game/vote")
async def cast_vote(req: VoteRequest):
    """人类玩家投票"""
    print(f"收到投票请求: voter={req.voter_id}, target={req.target_id}")
    
    if req.voter_id not in game.alive_players:
        return {"status": "error", "message": "玩家已死亡"}
    
    if req.voter_id in game.votes:
        return {"status": "already_voted"}
    
    game.record_vote(req.voter_id, req.target_id)
    
    await broadcast({
        "type": "VOTE_CAST",
        "data": {
            "player_id": req.voter_id,
            "content": f"P{req.voter_id} 投票给了 P{req.target_id}"
        }
    })
    
    # 检查是否所有存活玩家都已投票
    if len(game.votes) == len(game.alive_players):
        await process_vote_result()
    else:
        # 让AI投票
        await auto_ai_votes()
    
    return {"status": "ok"}

@app.post("/api/game/ai/speak")
async def ai_speak(req: AISpeakRequest):
    """AI发言的HTTP接口"""
    await ai_speak_internal(req.player_id, req.speech, req.thought)
    return {"status": "ok"}

async def auto_ai_votes():
    """让所有AI自动投票"""
    print(f"[AI投票] 开始，存活玩家: {game.alive_players}, 已投票: {list(game.votes.keys())}")
    
    for pid in game.alive_players:
        if pid != human_player_id and pid not in game.votes:
            candidates = [p for p in game.alive_players if p != pid]
            if candidates:
                target = random.choice(candidates)
                game.record_vote(pid, target)
                
                await broadcast({
                    "type": "VOTE_CAST",
                    "data": {
                        "player_id": pid,
                        "content": f"P{pid} 投票给了 P{target}"
                    }
                })
    
    # 检查投票是否完成（所有存活玩家都已投票）
    if len(game.votes) == len(game.alive_players):
        await process_vote_result()


async def auto_ai_votes_rerun(exclude_players):
    """平票后让AI重新投票（排除平票候选人）"""
    print(f"[AI重新投票] 排除玩家: {exclude_players}")
    
    # 平票后重置投票记录
    game.votes = {}
    
    # 获取可以投票的玩家（排除平票候选人）
    eligible_voters = [p for p in game.alive_players if p not in exclude_players]
    print(f"[AI重新投票] 可投票玩家: {eligible_voters}")
    
    for pid in eligible_voters:
        if pid != human_player_id and pid not in game.votes:
            # 可选目标：排除自己和平票候选人
            candidates = [p for p in game.alive_players if p != pid and p not in exclude_players]
            if candidates:
                target = random.choice(candidates)
                game.record_vote(pid, target)
                
                await broadcast({
                    "type": "VOTE_CAST",
                    "data": {
                        "player_id": pid,
                        "content": f"P{pid} 投票给了 P{target}"
                    }
                })
    
    # 检查投票是否完成（所有可投票玩家都已投票）
    if len(game.votes) == len(eligible_voters):
        await process_vote_result()


async def process_vote_result():
    """处理投票结果，决定谁被淘汰"""
    global current_timeout_task
    
    # 等待人类玩家投票（如果还没投）
    if human_player_id in game.alive_players and human_player_id not in game.votes:
        print("[投票] 等待人类玩家投票...")
        # 给人类玩家30秒时间投票
        await broadcast({
            "type": "VOTE_PHASE",
            "data": {"content": "请投票！你有30秒时间"}
        })
        try:
            await asyncio.wait_for(_wait_for_human_vote(), timeout=30)
        except asyncio.TimeoutError:
            print("[投票] 人类玩家超时，随机投票")
            # 超时随机投票
            candidates = [p for p in game.alive_players if p != human_player_id]
            if candidates:
                random_target = random.choice(candidates)
                game.record_vote(human_player_id, random_target)
    
    if len(game.votes) != len(game.alive_players):
        print(f"[投票] 投票未完成: 已投票{len(game.votes)}/{len(game.alive_players)}")
        return
    
    print(f"[投票] 投票结果: {game.votes}")
    
    # 统计票数
    vote_count = {}
    for target in game.votes.values():
        vote_count[target] = vote_count.get(target, 0) + 1
    
    if not vote_count:
        return
    
    max_votes = max(vote_count.values())
    candidates = [pid for pid, count in vote_count.items() if count == max_votes]
    
    print(f"[投票] 最高票数: {max_votes}, 候选人: {candidates}")
    
    if len(candidates) == 1:
        eliminated = candidates[0]
        
        # 淘汰玩家
        game.eliminate(eliminated)
        
        await broadcast({
            "type": "ELIMINATION",
            "data": {
                "player_id": eliminated,
                "content": f"P{eliminated} 被投票放逐！"
            }
        })
        
        # 检查游戏是否结束
        if game.phase == GamePhase.GAME_OVER:
            winner_text = game.get_winner()
            await broadcast({
                "type": "GAME_OVER",
                "data": {"winner": winner_text}
            })
            return
        
        # 进入夜晚阶段
        await start_night_phase()
        
    else:
        # 平票处理
        print(f"[投票] 平票，候选人: {candidates}，重新投票")
        
        await broadcast({
            "type": "NO_ELIMINATION",
            "data": {"content": f"平票（P{', P'.join(map(str, candidates))}），请其他玩家重新投票"}
        })
        
        # 让AI重新投票（排除平票候选人）
        await auto_ai_votes_rerun(candidates)


async def _wait_for_human_vote():
    """等待人类玩家投票（简易实现）"""
    # 这个函数会被 process_vote_result 中的 wait_for 调用
    # 实际的人类投票通过 WebSocket 的 VOTE_CAST 消息处理
    # 这里简单等待，实际检查在别处完成
    while human_player_id not in game.votes:
        await asyncio.sleep(0.5)


async def start_night_phase():
    """开始夜晚阶段"""
    global game
    
    print("\n[夜晚] 开始夜晚阶段...")
    
    # 广播夜晚开始
    await broadcast({
        "type": "NIGHT_START",
        "data": {"content": "夜晚降临，请等待..."}
    })
    
    # 重要：先切换到狼人阶段
    game.phase = GamePhase.NIGHT_WOLF
    
    # 1. 狼人杀人 - 改为使用 handle_wolf_action
    await handle_wolf_action()
    
    # 2. 预言家查验 - 改为使用 handle_seer_action
    game.phase = GamePhase.NIGHT_SEER
    await handle_seer_action()
    
    # 3. 女巫行动
    game.phase = GamePhase.NIGHT_WITCH
    await handle_witch_action()
    
    # 4. 解决夜晚结果
    deaths = game.resolve_night()
    
    # 广播夜晚结果
    if deaths:
        for died in deaths:
            await broadcast({
                "type": "NIGHT_RESULT",
                "data": {
                    "player_id": died,
                    "content": f"天亮了，P{died} 在夜晚死亡"
                }
            })
    else:
        await broadcast({
            "type": "NIGHT_RESULT",
            "data": {
                "player_id": None,
                "content": "天亮了，昨晚是个平安夜"
            }
        })
    
    # 检查游戏是否结束
    if game.phase == GamePhase.GAME_OVER:
        winner_text = game.get_winner()
        await broadcast({
            "type": "GAME_OVER",
            "data": {"winner": winner_text}
        })
        return
    
    # 开始白天阶段
    await start_day_phase()


async def auto_wolf_kill():
    """AI狼人自动选择杀人目标"""
    wolves = [p for p in game.players if p["role"] == Role.WEREWOLF and p["alive"]]
    
    if not wolves:
        return
    
    # 狼人协商杀人（选择随机非狼人玩家）
    alive_non_wolves = [p["id"] for p in game.players if p["alive"] and p["role"] != Role.WEREWOLF]
    
    if alive_non_wolves:
        target = random.choice(alive_non_wolves)
        for wolf in wolves:
            game.record_wolf_vote(wolf["id"], target)
        
        print(f"[狼人] 狼人选择击杀 {target}")
        await broadcast({
            "type": "NIGHT_ACTION",
            "data": {"content": f"狼人选择了目标..."}
        })


async def auto_seer_check():
    """AI预言家自动查验"""
    seers = [p for p in game.players if p["role"] == Role.SEER and p["alive"]]
    
    if not seers:
        return
    
    # 随机选择一个存活玩家查验
    alive_players = [p["id"] for p in game.players if p["alive"] and p["id"] != seers[0]["id"]]
    
    if alive_players:
        target = random.choice(alive_players)
        game.record_seer_check(target)
        
        # 获取查验结果
        result = game.get_seer_result()
        is_wolf = (result == Role.WEREWOLF)
        
        print(f"[预言家] 查验 {target}, 角色: {result}, 是否狼人: {is_wolf}")
        
        # 保存查验结果到AI内心独白和记忆
        check_result = f"我查验了{target}号，他是{'狼人' if is_wolf else '好人'}"
        ai_thoughts[seers[0]["id"]] = check_result
        
        # 同时保存到memory service，让其他AI知道这个信息
        try:
            if memory_db:
                memory_db.save_message(
                    seers[0]["id"], 
                    Role.SEER.value, 
                    f"我在夜晚查验了{target}号，他是{'狼人' if is_wolf else '好人'}。",
                    None
                )
        except Exception as e:
            print(f"保存预言家信息失败: {e}")

async def auto_witch_action():
    """AI女巫自动行动"""
    witches = [p for p in game.players if p["role"] == Role.WITCH and p["alive"]]
    
    if not witches:
        return
    
    print(f"[女巫] 被杀目标: {game.killed_target}")
    
    # 如果有被杀目标，使用解药救人（为了方便测试，直接救）
    if game.killed_target:
        # 简单策略：总是救第一晚被杀的人
        game.witch_save = game.killed_target
        ai_thoughts[witches[0]["id"]] = f"我使用解药救了{game.killed_target}号"
        print(f"[女巫] 救了 {game.killed_target}")
        # 清空killed_target，表示被救了
        game.killed_target = None
    
    # 随机决定是否毒人（20%概率）
    if random.random() < 0.2:
        alive_players = [p["id"] for p in game.players if p["alive"] and p["id"] != witches[0]["id"]]
        if alive_players:
            poison_target = random.choice(alive_players)
            game.witch_poison = poison_target
            if witches[0]["id"] in ai_thoughts:
                ai_thoughts[witches[0]["id"]] += f"，并毒死了{poison_target}号"
            else:
                ai_thoughts[witches[0]["id"]] = f"我毒死了{poison_target}号"
            print(f"[女巫] 毒死了 {poison_target}")


async def start_day_phase():
    """开始白天阶段"""
    global current_timeout_task
    
    game.start_day_phase()
    
    await broadcast({
        "type": "NEXT_DAY",
        "data": {
            "round": game.round,
            "current": game.current_speaker,
            "alive_players": game.alive_players
        }
    })
    
    # 触发第一个发言者
    if game.current_speaker == human_player_id:
        await broadcast({
            "type": "YOUR_TURN",
            "data": {"current": game.current_speaker}
        })
        if current_timeout_task:
            current_timeout_task.cancel()
        current_timeout_task = asyncio.create_task(human_timeout_task(human_player_id, 60))
    else:
        asyncio.create_task(handle_ai_turn(game.current_speaker))

@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: int):
    global current_timeout_task
    
    await websocket.accept()
    connections[player_id] = websocket
    print(f"玩家 {player_id} 已连接 WebSocket")
    
    is_human = (player_id == human_player_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            print(f"收到玩家 {player_id} 的消息: {data}")
            
            # 新增：处理夜晚行动消息
            if is_human and game.phase in [GamePhase.NIGHT_WOLF, GamePhase.NIGHT_SEER, GamePhase.NIGHT_WITCH]:
                try:
                    msg = json.loads(data) if isinstance(data, str) and data.startswith('{') else None
                    if msg and "night_action" in msg:
                        action_type = msg.get("action_type")
                        target = msg.get("target")
                        
                        # 处理女巫行动
                        if action_type == "witch_save":
                            human_night_action["witch_save"] = target
                            human_night_action_received.set()
                        elif action_type == "witch_poison":
                            human_night_action["witch_poison"] = target
                            human_night_action_received.set()
                        else:
                            human_night_action[action_type] = target
                            human_night_action_received.set()
                        
                        await websocket.send_text(json.dumps({
                            "type": "NIGHT_ACTION_CONFIRM",
                            "data": {"content": f"已选择目标 P{target}"}
                        }))
                        continue
                except:
                    pass
            
            # 检查是否是当前发言者
            if is_human and game.phase == GamePhase.DAY_DISCUSSION:
                if game.current_speaker == human_player_id:
                    # 人类玩家发言
                    if current_timeout_task:
                        current_timeout_task.cancel()
                    
                    # 广播发言
                    await broadcast({
                        "type": "SPEECH",
                        "data": {
                            "player_id": human_player_id,
                            "content": data
                        }
                    })
                    
                    # 轮到下一个
                    next_speaker = game.next_speaker()
                    
                    if next_speaker:
                        if next_speaker == human_player_id:
                            await broadcast({
                                "type": "YOUR_TURN",
                                "data": {"current": game.current_speaker}
                            })
                            current_timeout_task = asyncio.create_task(human_timeout_task(human_player_id, 60))
                        else:
                            await broadcast({
                                "type": "NEXT_SPEAKER",
                                "data": {"current": next_speaker}
                            })
                            asyncio.create_task(handle_ai_turn(next_speaker))
                    else:
                        # 发言结束
                        game.phase = GamePhase.DAY_VOTE
                        await broadcast({
                            "type": "VOTE_PHASE",
                            "data": {"content": "发言结束，请投票"}
                        })
                        await auto_ai_votes()
                else:
                    await websocket.send_text(json.dumps({
                        "type": "ERROR",
                        "data": {"content": "还没轮到你发言"}
                    }))
            
    except WebSocketDisconnect:
        connections.pop(player_id, None)
        print(f"玩家 {player_id} 断开连接")