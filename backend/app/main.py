from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import asyncio
from dotenv import load_dotenv
from app.core.game_state import GameStateMachine, GamePhase, Role

load_dotenv()

game = GameStateMachine()
human_player_id = 1
connections = {}
ai_thoughts = {}
current_timeout_task = None

# =====================
# 超时任务函数
# =====================
async def human_timeout_task(player_id: int, speech_timeout: int = 30):
    global current_timeout_task
    await asyncio.sleep(speech_timeout)
    
    if game.current_speaker == player_id and game.phase == GamePhase.DAY_DISCUSSION:
        print(f"⏰ 人类玩家 {player_id} 超时未发言，自动跳过")
        
        await broadcast({
            "type": "TIMEOUT",
            "data": {"player_id": player_id, "message": "发言超时，自动跳过"}
        })
        
        next_speaker = game.next_speaker()
        if next_speaker:
            if next_speaker == human_player_id:
                await broadcast({
                    "type": "YOUR_TURN",
                    "data": {"speaker": next_speaker, "time_limit": 30}
                })
                current_timeout_task = asyncio.create_task(human_timeout_task(human_player_id, 30))
            else:
                await broadcast({
                    "type": "NEXT_SPEAKER",
                    "data": {"speaker": next_speaker}
                })
        elif game.phase == GamePhase.DAY_VOTE:
            await broadcast({
                "type": "VOTE_PHASE",
                "data": {"message": "发言结束，开始投票"}
            })


# =====================
# 广播函数
# =====================
async def broadcast(payload: dict):
    msg = json.dumps(payload)
    dead = []
    for pid, conn in connections.items():
        try:
            await conn.send_text(msg)
        except:
            dead.append(pid)
    for pid in dead:
        connections.pop(pid, None)


# =====================
# 生命周期
# =====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("服务器启动成功")
    yield
    print("服务器关闭")


app = FastAPI(title="Nexus-Werewolf AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================
# API 接口
# =====================
@app.get("/api/health")
async def health():
    return {"status": "ok", "message": "Nexus-Werewolf AI Backend"}


@app.get("/api/game/status")
async def game_status():
    return {
        "phase": game.phase,
        "alive_players": game.alive_players,
        "current_speaker": game.current_speaker,
        "round": game.round,
        "human_player": human_player_id,
        "ai_thoughts": ai_thoughts
    }


@app.get("/api/game/trust-matrix")
async def get_trust_matrix():
    try:
        from app.services.memory_service import memory_db
        matrix = memory_db.get_trust_matrix()
        return {"trust_matrix": matrix}
    except:
        sample_matrix = {}
        for i in range(1, 7):
            sample_matrix[str(i)] = {}
            for j in range(1, 7):
                if i != j:
                    sample_matrix[str(i)][str(j)] = 50
        return {"trust_matrix": sample_matrix, "note": "示例数据"}


@app.post("/api/game/start")
async def start_game():
    global game, current_timeout_task
    
    player_ids = [1, 2, 3, 4, 5, 6]
    roles = game.assign_roles(player_ids)

    for player_id, conn in connections.items():
        if player_id in roles:
            await conn.send_text(json.dumps({
                "type": "ROLE_ASSIGNMENT",
                "data": {"player_id": player_id, "role": roles[player_id]}
            }))

    game.start_day_phase()

    if game.current_speaker == human_player_id:
        await broadcast({
            "type": "YOUR_TURN",
            "data": {"speaker": game.current_speaker, "time_limit": 30}
        })
        current_timeout_task = asyncio.create_task(human_timeout_task(human_player_id, 30))

    return {
        "status": "ok",
        "phase": str(game.phase),
        "first_speaker": game.current_speaker,
        "human_player": human_player_id,
        "roles": {str(k): str(v) for k, v in roles.items()}
    }


@app.post("/api/game/ai/speak")
async def ai_speak(player_id: int, speech: str, thought: str, vote_target: int = None):
    global current_timeout_task
    
    ai_thoughts[player_id] = thought
    
    await broadcast({
        "type": "AI_SPEECH",
        "data": {
            "player_id": player_id,
            "speech": speech,
            "thought": thought
        }
    })
    
    if game.phase == GamePhase.DAY_VOTE and vote_target:
        game.record_vote(player_id, vote_target)
    
    if game.phase == GamePhase.DAY_DISCUSSION and game.current_speaker == player_id:
        next_speaker = game.next_speaker()
        if next_speaker:
            if next_speaker == human_player_id:
                await broadcast({
                    "type": "YOUR_TURN",
                    "data": {"speaker": next_speaker, "time_limit": 30}
                })
                if current_timeout_task:
                    current_timeout_task.cancel()
                current_timeout_task = asyncio.create_task(human_timeout_task(human_player_id, 30))
            else:
                await broadcast({
                    "type": "NEXT_SPEAKER",
                    "data": {"speaker": next_speaker}
                })
        elif game.phase == GamePhase.DAY_VOTE:
            await broadcast({
                "type": "VOTE_PHASE",
                "data": {"message": "发言结束，开始投票"}
            })
    
    return {"status": "ok"}


@app.post("/api/game/vote")
async def cast_vote(voter_id: int, target_id: int):
    game.record_vote(voter_id, target_id)

    if len(game.votes) == len(game.alive_players):
        eliminated = game.calculate_elimination()
        if eliminated:
            game.eliminate(eliminated)
            await broadcast({
                "type": "ELIMINATION",
                "data": {"eliminated": eliminated, "phase": str(game.phase)}
            })
            
            if game.phase == GamePhase.GAME_OVER:
                winner = game.get_winner()
                await broadcast({
                    "type": "GAME_OVER",
                    "data": {"winner": winner}
                })
        else:
            game.start_night_phase()
            await broadcast({
                "type": "PHASE_CHANGE",
                "data": {"phase": str(game.phase), "message": "进入夜晚阶段"}
            })

    return {"status": "ok", "votes": game.votes}


@app.post("/api/game/night/wolf")
async def wolf_vote(wolf_id: int, target_id: int):
    if game.phase != GamePhase.NIGHT_WOLF:
        return {"error": "Not in wolf night phase", "status": "error"}
    
    game.record_wolf_vote(wolf_id, target_id)
    
    werewolves = [p for p in game.players if p["role"] == Role.WEREWOLF and p["alive"]]
    
    if len(game.wolf_votes) == len(werewolves):
        killed = game.resolve_wolf_kill()
        game.phase = GamePhase.NIGHT_SEER
        await broadcast({
            "type": "PHASE_CHANGE",
            "data": {"phase": "NIGHT_SEER", "message": "预言家请查验"}
        })
        return {"status": "ok", "killed": killed, "next_phase": "NIGHT_SEER"}
    
    return {"status": "ok", "votes_received": len(game.wolf_votes)}


@app.post("/api/game/night/seer")
async def seer_check(target_id: int):
    if game.phase != GamePhase.NIGHT_SEER:
        return {"error": "Not in seer night phase", "status": "error"}
    
    game.record_seer_check(target_id)
    result = game.get_seer_result()
    
    killed = game.resolve_night()
    
    await broadcast({
        "type": "NIGHT_RESULT",
        "data": {"killed": killed, "seer_result": result, "phase": str(game.phase)}
    })
    
    return {
        "status": "ok",
        "target": target_id,
        "result": result,
        "killed": killed,
        "phase": str(game.phase)
    }


@app.post("/api/game/next_speaker")
async def next_speaker():
    """手动切换到下一个发言者（用于测试）"""
    if game.phase == GamePhase.DAY_DISCUSSION:
        next_sp = game.next_speaker()
        if next_sp:
            await broadcast({
                "type": "NEXT_SPEAKER",
                "data": {"speaker": next_sp}
            })
            return {"status": "ok", "next_speaker": next_sp}
    return {"status": "no_next_speaker"}


# =====================
# WebSocket
# =====================
@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: int):
    global current_timeout_task
    
    await websocket.accept()
    connections[player_id] = websocket
    print(f"玩家 {player_id} 已连接")
    
    is_human = (player_id == human_player_id)

    try:
        while True:
            data = await websocket.receive_text()
            print(f"收到玩家 {player_id}: {data}")
            
            if is_human and game.phase == GamePhase.DAY_DISCUSSION:
                if game.current_speaker == human_player_id:
                    if current_timeout_task:
                        current_timeout_task.cancel()
                    
                    await broadcast({
                        "type": "SPEECH",
                        "data": {
                            "player_id": human_player_id,
                            "content": data,
                            "is_human": True
                        }
                    })
                    
                    next_speaker = game.next_speaker()
                    if next_speaker:
                        if next_speaker == human_player_id:
                            await broadcast({
                                "type": "YOUR_TURN",
                                "data": {"speaker": next_speaker, "time_limit": 30}
                            })
                            current_timeout_task = asyncio.create_task(
                                human_timeout_task(human_player_id, 30)
                            )
                        else:
                            await broadcast({
                                "type": "NEXT_SPEAKER",
                                "data": {"speaker": next_speaker}
                            })
                    elif game.phase == GamePhase.DAY_VOTE:
                        await broadcast({
                            "type": "VOTE_PHASE",
                            "data": {"message": "发言结束，开始投票"}
                        })
                else:
                    await websocket.send_text(json.dumps({
                        "type": "ERROR",
                        "data": {"message": "还没轮到你发言"}
                    }))
            
            await websocket.send_text(json.dumps({"type": "ACK", "data": "received"}))

    except WebSocketDisconnect:
        if current_timeout_task:
            current_timeout_task.cancel()
        connections.pop(player_id, None)
        print(f"玩家 {player_id} 断开")