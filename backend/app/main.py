from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import asyncio
import random
from dotenv import load_dotenv
from app.core.game_state import GameStateMachine, GamePhase, Role
from app.services.llm_service import get_ai_response_with_timeout
from app.services.memory_service import memory_db

load_dotenv()

game = GameStateMachine()
human_player_id = 1
human_night_action = {}
human_night_action_received = asyncio.Event()
connections = {}
ai_thoughts = {}
current_timeout_task = None

_is_day_phase_starting = False
_is_night_phase_starting = False
_is_vote_processing = False

async def broadcast(message):
    dead = []
    for pid, conn in connections.items():
        try:
            await conn.send_text(json.dumps(message))
        except:
            dead.append(pid)
    for pid in dead:
        connections.pop(pid, None)

async def human_timeout_task(player_id: int, speech_timeout: int = 60):
    global current_timeout_task
    await asyncio.sleep(speech_timeout)
    if game.current_speaker == player_id and game.phase == GamePhase.DAY_DISCUSSION:
        print(f"⏰ 人类玩家 {player_id} 超时")
        await broadcast({"type": "TIMEOUT", "data": {"player_id": player_id, "content": "发言超时，自动跳过"}})
        next_speaker = game.next_speaker()
        if next_speaker:
            if next_speaker == human_player_id:
                await broadcast({"type": "YOUR_TURN", "data": {"current": game.current_speaker}})
                current_timeout_task = asyncio.create_task(human_timeout_task(human_player_id, 60))
            else:
                await broadcast({"type": "NEXT_SPEAKER", "data": {"current": next_speaker}})
                asyncio.create_task(handle_ai_turn(next_speaker))
        else:
            game.phase = GamePhase.DAY_VOTE
            await broadcast({"type": "VOTE_PHASE", "data": {"content": "发言结束，请投票"}})
            await auto_ai_votes()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 服务器启动")
    yield
    print("🛑 服务器关闭")

app = FastAPI(title="Werewolf AI", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
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
    try:
        if memory_db:
            matrix = memory_db.get_trust_matrix()
            return {"trust_matrix": matrix}
    except:
        pass
    matrix = {str(i): {str(j): 50 for j in range(1, 7)} for i in range(1, 7)}
    return {"trust_matrix": matrix}

@app.get("/api/ai/thought/{player_id}")
async def get_ai_thought(player_id: int):
    return {"thought": ai_thoughts.get(player_id, "暂无内心独白")}

@app.post("/api/game/start")
async def start_game():
    global game, current_timeout_task, ai_thoughts, human_night_action, human_night_action_received
    global _is_day_phase_starting, _is_night_phase_starting
    
    _is_day_phase_starting = False
    _is_night_phase_starting = False
    game = GameStateMachine()
    ai_thoughts = {}
    human_night_action = {}
    human_night_action_received.clear()
    
    try:
        if memory_db and memory_db.redis_available:
            memory_db.redis.flushall()
    except:
        pass
    
    player_ids = [1, 2, 3, 4, 5, 6]
    roles = game.assign_roles(player_ids)
    werewolves = [pid for pid, role in roles.items() if role == Role.WEREWOLF]
    print(f"🐺 狼人: {werewolves}")
    print(f"📋 角色: {roles}")

    for player_id, conn in connections.items():
        if player_id in roles:
            role_value = roles[player_id].value
            msg = {"type": "ROLE_ASSIGNMENT", "data": {"player_id": player_id, "role": role_value}}
            if roles[player_id] == Role.WEREWOLF:
                msg["data"]["werewolf_teammates"] = [pid for pid in werewolves if pid != player_id]
            await conn.send_text(json.dumps(msg))

    await start_first_night()
    return {"status": "ok"}

async def start_first_night():
    print("\n🌙 第一夜...")
    await broadcast({"type": "NIGHT_START", "data": {"content": "第一夜降临..."}})
    game.phase = GamePhase.NIGHT_WOLF
    await handle_wolf_action()
    game.phase = GamePhase.NIGHT_SEER
    await handle_seer_action()
    game.phase = GamePhase.NIGHT_GUARDIAN
    await handle_guardian_action()
    killed = game.resolve_night()
    if killed:
        await broadcast({"type": "NIGHT_RESULT", "data": {"player_id": killed, "content": f"天亮了，P{killed} 在夜晚死亡"}})
    else:
        await broadcast({"type": "NIGHT_RESULT", "data": {"player_id": None, "content": "天亮了，昨晚是个平安夜"}})
    await start_day_phase()

async def start_night_phase():
    global _is_night_phase_starting
    if _is_night_phase_starting:
        print("⚠️ 夜晚阶段已在执行，跳过")
        return
    _is_night_phase_starting = True
    try:
        print(f"\n🌙 第 {game.round} 轮夜晚...")
        await broadcast({"type": "NIGHT_START", "data": {"content": "夜晚降临..."}})
        game.phase = GamePhase.NIGHT_WOLF
        await handle_wolf_action()
        game.phase = GamePhase.NIGHT_SEER
        await handle_seer_action()
        game.phase = GamePhase.NIGHT_GUARDIAN
        await handle_guardian_action()
        killed = game.resolve_night()
        if killed:
            await broadcast({"type": "NIGHT_RESULT", "data": {"player_id": killed, "content": f"天亮了，P{killed} 在夜晚死亡"}})
        else:
            await broadcast({"type": "NIGHT_RESULT", "data": {"player_id": None, "content": "天亮了，昨晚是个平安夜"}})
        
        print(f"📌 夜晚结束，当前阶段: {game.phase}, 存活玩家: {game.alive_players}")
        
        # ✅ 检查游戏是否结束
        if game.phase == GamePhase.GAME_OVER:
            winner = game.get_winner()
            print(f"🏆 游戏结束！{winner}")
            await broadcast({
                "type": "GAME_OVER",
                "data": {"winner": winner}
            })
            return
        
        # 进入白天
        print("🌅 准备进入白天...")
        await start_day_phase()
            
    except Exception as e:
        print(f"❌ 夜晚错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        _is_night_phase_starting = False

async def handle_wolf_action():
    wolves = [p for p in game.players if p["role"] == Role.WEREWOLF and p["alive"]]
    if not wolves:
        return
    human_is_wolf = human_player_id in [w["id"] for w in wolves]
    if human_is_wolf:
        candidates = [p["id"] for p in game.players if p["alive"] and p["role"] != Role.WEREWOLF]
        await broadcast({"type": "NIGHT_CHOOSE_TARGET", "data": {"action": "wolf_kill", "candidates": candidates, "content": "你是狼人，选择击杀目标"}})
        try:
            await asyncio.wait_for(human_night_action_received.wait(), timeout=30)
            target = human_night_action.get("wolf_kill")
            human_night_action_received.clear()
            if target and target in candidates:
                for wolf in wolves:
                    game.record_wolf_vote(wolf["id"], target)
                print(f"🐺 狼人击杀 P{target}")
                return
        except:
            print("⏰ 狼人超时")
    candidates = [p["id"] for p in game.players if p["alive"] and p["role"] != Role.WEREWOLF]
    if candidates:
        target = random.choice(candidates)
        for wolf in wolves:
            game.record_wolf_vote(wolf["id"], target)
        print(f"🐺 AI狼人击杀 P{target}")

async def handle_seer_action():
    seers = [p for p in game.players if p["role"] == Role.SEER and p["alive"]]
    if not seers:
        return
    candidates = [p["id"] for p in game.players if p["alive"] and p["id"] != seers[0]["id"]]
    if candidates:
        target = random.choice(candidates)
        game.record_seer_check(target)
        print(f"🔮 AI预言家查验了 P{target}")

async def handle_guardian_action():
    guardians = [p for p in game.players if p["role"] == Role.GUARDIAN and p["alive"]]
    if not guardians:
        return
    candidates = [p["id"] for p in game.players if p["alive"] and p["id"] != guardians[0]["id"]]
    if candidates:
        target = random.choice(candidates)
        game.record_guardian_protect(target)
        print(f"🛡️ AI守卫守护了 P{target}")

async def handle_ai_turn(player_id: int):
    print(f"🤖 AI {player_id} 发言")
    
    player_role = None
    for p in game.players:
        if p["id"] == player_id:
            player_role = p["role"]
            break
    
    if not player_role:
        await handle_ai_turn_fallback(player_id, False)
        return
    
    # ========== 判断是否是第一个发言者 ==========
    is_first_speaker = False
    if hasattr(game, 'speak_order') and game.speak_order:
        is_first_speaker = (game.current_speaker == game.speak_order[0])
    
    # ========== 第一个发言：直接使用固定话术 ==========
    if is_first_speaker:
        speeches = ["我是好人，过", "没信息，先听大家说", "过", "先听大家聊", "我是平民，过"]
        speech = random.choice(speeches)
        thought = "第一个发言，简单过一下"
        ai_thoughts[player_id] = thought
        print(f"💬 AI {player_id}: {speech}")
        await broadcast({"type": "SPEECH", "data": {"player_id": player_id, "content": speech}})
        
        next_speaker = game.next_speaker()
        if next_speaker:
            if next_speaker == human_player_id:
                await broadcast({"type": "YOUR_TURN", "data": {"current": game.current_speaker}})
                if current_timeout_task:
                    current_timeout_task.cancel()
                current_timeout_task = asyncio.create_task(human_timeout_task(human_player_id, 60))
            else:
                await broadcast({"type": "NEXT_SPEAKER", "data": {"current": next_speaker}})
                asyncio.create_task(handle_ai_turn(next_speaker))
        else:
            game.phase = GamePhase.DAY_VOTE
            await broadcast({"type": "VOTE_PHASE", "data": {"content": "发言结束，请投票"}})
            await auto_ai_votes()
        return
    
    # ========== 非第一个发言：正常调用 AI ==========
    all_players = [1, 2, 3, 4, 5, 6]
    dead_players = [pid for pid in all_players if pid not in game.alive_players]
    
    # 获取预言家查验结果
    seer_check_info = ""
    if player_role == Role.SEER and game.seer_target:
        target = game.seer_target
        result = game.get_seer_result()
        is_wolf = (result == Role.WEREWOLF)
        if result:
            seer_check_info = f"你昨晚查验了 {target} 号，他是{'狼人' if is_wolf else '好人'}。你必须说真话！"
    
    game_state = f"""第{game.round}天白天讨论阶段。
存活玩家: {game.alive_players}
已淘汰玩家: {dead_players}（不要提已死的人）

你是{player_id}号玩家，你的身份是{player_role.value}。
{seer_check_info}
"""
    
    history = ""
    if memory_db:
        full_history = memory_db.get_full_context_for_ai()
        lines = full_history.split('\n')
        if len(lines) > 15:
            lines = lines[-15:]
        history = '\n'.join(lines)
    
    try:
        response = await get_ai_response_with_timeout(
            player_id=player_id,
            role=player_role.value,
            game_state=game_state,
            history=history,
            timeout=15
        )
        
        speech = response.get("speech", "我是好人，过")
        thought = response.get("thought", "思考中...")
        
        if len(speech) > 80:
            speech = speech[:80]
        
        ai_thoughts[player_id] = thought
        
        if memory_db:
            memory_db.save_message(player_id, player_role.value, speech, response.get("trust_scores"))
        
        await ai_speak_internal(player_id, speech, thought)
        
    except Exception as e:
        print(f"❌ AI失败: {e}")
        await handle_ai_turn_fallback(player_id, False)

async def handle_ai_turn_fallback(player_id: int, is_first_speaker: bool = False):
    await asyncio.sleep(1)
    
    if is_first_speaker:
        speeches = ["我是好人，过", "没信息，先听大家说", "过"]
    else:
        speeches = [f"我是{player_id}号，需要更多信息。", f"{player_id}号，先观察。", f"我是{player_id}号，跟票。"]
    
    speech = random.choice(speeches)
    thought = f"AI {player_id} 降级发言"
    ai_thoughts[player_id] = thought
    await ai_speak_internal(player_id, speech, thought)

async def ai_speak_internal(player_id: int, speech: str, thought: str):
    global current_timeout_task
    ai_thoughts[player_id] = thought
    await broadcast({"type": "SPEECH", "data": {"player_id": player_id, "content": speech}})
    print(f"💬 AI {player_id}: {speech}")
    
    if game.phase == GamePhase.DAY_DISCUSSION and game.current_speaker == player_id:
        next_speaker = game.next_speaker()
        print(f"当前发言者 {player_id}，下一个发言者: {next_speaker}")
        
        if next_speaker is not None:
            if next_speaker == human_player_id:
                await broadcast({"type": "YOUR_TURN", "data": {"current": game.current_speaker}})
                if current_timeout_task:
                    current_timeout_task.cancel()
                current_timeout_task = asyncio.create_task(human_timeout_task(human_player_id, 60))
            else:
                await broadcast({"type": "NEXT_SPEAKER", "data": {"current": next_speaker}})
                asyncio.create_task(handle_ai_turn(next_speaker))
        else:
            print("所有玩家发言完毕，进入投票阶段")
            game.phase = GamePhase.DAY_VOTE
            await broadcast({"type": "VOTE_PHASE", "data": {"content": "发言结束，请投票"}})
            await auto_ai_votes()

async def start_day_phase():
    global _is_day_phase_starting, current_timeout_task
    if _is_day_phase_starting:
        print("⚠️ 白天阶段已在执行，跳过")
        return
    _is_day_phase_starting = True
    try:
        game.start_day_phase()
        print(f"☀️ 第 {game.round} 天，发言顺序: {game.speak_order}")
        
        await broadcast({
            "type": "NEXT_DAY",
            "data": {
                "round": game.round,
                "current": game.current_speaker,
                "alive_players": game.alive_players
            }
        })
        
        await asyncio.sleep(0.5)
        
        if game.current_speaker == human_player_id:
            await broadcast({"type": "YOUR_TURN", "data": {"current": game.current_speaker}})
            current_timeout_task = asyncio.create_task(human_timeout_task(human_player_id, 60))
        else:
            asyncio.create_task(handle_ai_turn(game.current_speaker))
    except Exception as e:
        print(f"❌ 白天错误: {e}")
    finally:
        _is_day_phase_starting = False

@app.post("/api/game/vote")
async def cast_vote(req: dict):
    voter_id = req.get("voter_id")
    target_id = req.get("target_id")
    
    if voter_id not in game.alive_players:
        return {"status": "error"}
    
    if voter_id in game.votes:
        return {"status": "already_voted"}
    
    game.record_vote(voter_id, target_id)
    await broadcast({"type": "VOTE_CAST", "data": {"player_id": voter_id, "content": f"P{voter_id} 投票给 P{target_id}"}})
    
    if len(game.votes) == len(game.alive_players):
        await process_vote_result()
    else:
        await auto_ai_votes()
    
    return {"status": "ok"}

async def auto_ai_votes():
    for pid in game.alive_players:
        if pid != human_player_id and pid not in game.votes:
            candidates = [p for p in game.alive_players if p != pid]
            if candidates:
                target = random.choice(candidates)
                game.record_vote(pid, target)
                await broadcast({"type": "VOTE_CAST", "data": {"player_id": pid, "content": f"P{pid} 投票给 P{target}"}})
    
    if len(game.votes) == len(game.alive_players):
        await process_vote_result()

async def process_vote_result():
    global _is_vote_processing
    
    if _is_vote_processing:
        print("⚠️ 投票处理已在执行，跳过")
        return
    
    _is_vote_processing = True
    
    try:
        if human_player_id in game.alive_players and human_player_id not in game.votes:
            await broadcast({"type": "VOTE_PHASE", "data": {"content": "请投票！"}})
            try:
                await asyncio.wait_for(_wait_for_human_vote(), timeout=30)
            except:
                candidates = [p for p in game.alive_players if p != human_player_id]
                if candidates:
                    random_target = random.choice(candidates)
                    game.record_vote(human_player_id, random_target)
                    await broadcast({"type": "VOTE_CAST", "data": {"player_id": human_player_id, "content": f"P{human_player_id} 投票给 P{random_target}"}})
        
        if len(game.votes) != len(game.alive_players):
            print(f"投票未完成: {len(game.votes)}/{len(game.alive_players)}")
            return
        
        vote_count = {}
        for target in game.votes.values():
            vote_count[target] = vote_count.get(target, 0) + 1
        
        if not vote_count:
            return
        
        max_votes = max(vote_count.values())
        candidates = [pid for pid, count in vote_count.items() if count == max_votes]
        
        print(f"投票结果: 最高票{max_votes}，候选人{candidates}")
        
        if len(candidates) == 1:
            eliminated = candidates[0]
            game.eliminate(eliminated)
            
            await broadcast({"type": "ELIMINATION", "data": {"player_id": eliminated, "content": f"P{eliminated} 被放逐！"}})
            
            if game.phase == GamePhase.GAME_OVER:
                winner = game.get_winner()
                await broadcast({"type": "GAME_OVER", "data": {"winner": winner}})
                return
            
            game.votes = {}
            await start_night_phase()
        else:
            await broadcast({"type": "NO_ELIMINATION", "data": {"content": "平票，重新投票"}})
            game.votes = {}
            await auto_ai_votes()
            
    except Exception as e:
        print(f"❌ 投票处理错误: {e}")
    finally:
        _is_vote_processing = False

async def _wait_for_human_vote():
    while human_player_id not in game.votes:
        await asyncio.sleep(0.5)

@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: int):
    global current_timeout_task
    
    await websocket.accept()
    connections[player_id] = websocket
    print(f"🔌 玩家 {player_id} 连接")
    is_human = (player_id == human_player_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            print(f"📨 收到 {player_id}: {data[:100]}")
            
            if is_human and game.phase in [GamePhase.NIGHT_WOLF, GamePhase.NIGHT_SEER, GamePhase.NIGHT_GUARDIAN]:
                try:
                    msg = json.loads(data)
                    if "night_action" in msg:
                        human_night_action[msg.get("action_type")] = msg.get("target")
                        human_night_action_received.set()
                        await websocket.send_text(json.dumps({"type": "NIGHT_ACTION_CONFIRM", "data": {"content": f"已选 P{msg.get('target')}"}}))
                        continue
                except:
                    pass
            
            if is_human and game.phase == GamePhase.DAY_DISCUSSION:
                if game.current_speaker == human_player_id:
                    if current_timeout_task:
                        current_timeout_task.cancel()
                    
                    await broadcast({"type": "SPEECH", "data": {"player_id": human_player_id, "content": data}})
                    
                    next_speaker = game.next_speaker()
                    if next_speaker:
                        if next_speaker == human_player_id:
                            await broadcast({"type": "YOUR_TURN", "data": {"current": game.current_speaker}})
                            current_timeout_task = asyncio.create_task(human_timeout_task(human_player_id, 60))
                        else:
                            await broadcast({"type": "NEXT_SPEAKER", "data": {"current": next_speaker}})
                            asyncio.create_task(handle_ai_turn(next_speaker))
                    else:
                        game.phase = GamePhase.DAY_VOTE
                        await broadcast({"type": "VOTE_PHASE", "data": {"content": "发言结束，请投票"}})
                        await auto_ai_votes()
                else:
                    await websocket.send_text(json.dumps({"type": "ERROR", "data": {"content": "还没轮到你"}}))
            
            if is_human and game.phase == GamePhase.DAY_VOTE and human_player_id not in game.votes:
                try:
                    target = int(data)
                    if target in game.alive_players and target != human_player_id:
                        game.record_vote(human_player_id, target)
                        await broadcast({"type": "VOTE_CAST", "data": {"player_id": human_player_id, "content": f"P{human_player_id} 投票给 P{target}"}})
                        if len(game.votes) == len(game.alive_players):
                            await process_vote_result()
                        else:
                            await auto_ai_votes()
                except:
                    pass
                    
    except WebSocketDisconnect:
        connections.pop(player_id, None)
        print(f"🔌 玩家 {player_id} 断开")