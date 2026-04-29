from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import os
from dotenv import load_dotenv
from app.core.game_state import GameStateMachine, Role, GamePhase

load_dotenv()

game = GameStateMachine()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("✅ 服务器启动成功")
    yield
    print("服务器关闭")

app = FastAPI(title="Nexus-Werewolf AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

connections = {}

@app.get("/api/health")
async def health():
    return {"status": "ok", "message": "Nexus-Werewolf AI Backend"}

@app.post("/api/game/start")
async def start_game():
    global game
    player_ids = [1, 2, 3, 4, 5, 6]
    roles = game.assign_roles(player_ids)

    for player_id, conn in connections.items():
        if player_id in roles:
            await conn.send_text(json.dumps({
                "type": "ROLE_ASSIGNMENT",
                "data": {"player_id": player_id, "role": roles[player_id]}
            }))

    game.start_day_phase()

    return {
        "message": "Game started",
        "phase": game.phase,
        "first_speaker": game.current_speaker,
        "roles": {str(k): v for k, v in roles.items()}
    }

@app.post("/api/game/night/wolf")
async def wolf_vote(wolf_id: int, target_id: int):
    \"\"\"狼人投票杀人\"\"\"
    if game.phase != GamePhase.NIGHT_WOLF:
        return {"error": "Not in wolf night phase"}
    
    game.record_wolf_vote(wolf_id, target_id)
    
    # 检查是否所有狼人都投票了
    werewolves = [p for p in game.players if p["role"] == Role.WEREWOLF and p["alive"]]
    if len(game.wolf_votes) == len(werewolves):
        killed = game.resolve_wolf_kill()
        game.phase = GamePhase.NIGHT_SEER
        return {"status": "votes recorded", "killed": killed, "next_phase": "NIGHT_SEER"}
    
    return {"status": "vote recorded"}

@app.post("/api/game/night/seer")
async def seer_check(target_id: int):
    \"\"\"预言家查验\"\"\"
    if game.phase != GamePhase.NIGHT_SEER:
        return {"error": "Not in seer night phase"}
    
    game.record_seer_check(target_id)
    result = game.get_seer_result()
    
    # 进入天亮结算
    killed = game.resolve_night()
    
    # 广播死亡消息
    for conn in connections.values():
        await conn.send_text(json.dumps({
            "type": "NIGHT_RESULT",
            "data": {"killed": killed, "seer_result": result}
        }))
    
    return {
        "status": "checked",
        "target": target_id,
        "result": result,
        "killed": killed,
        "phase": game.phase
    }

@app.post("/api/game/vote")
async def cast_vote(voter_id: int, target_id: int):
    game.record_vote(voter_id, target_id)

    if len(game.votes) == len(game.alive_players):
        eliminated = game.calculate_elimination()
        if eliminated:
            game.eliminate(eliminated)
            for conn in connections.values():
                await conn.send_text(json.dumps({
                    "type": "ELIMINATION",
                    "data": {"eliminated": eliminated, "phase": game.phase}
                }))
            
            # 检查游戏是否结束
            if game.phase == GamePhase.GAME_OVER:
                winner = game.get_winner()
                for conn in connections.values():
                    await conn.send_text(json.dumps({
                        "type": "GAME_OVER",
                        "data": {"winner": winner}
                    }))
        else:
            # 平票，进入下一轮
            game.start_night_phase()

    return {"status": "voted", "votes": game.votes}

@app.get("/api/game/status")
async def game_status():
    return {
        "phase": game.phase,
        "alive_players": game.alive_players,
        "current_speaker": game.current_speaker,
        "round": game.round
    }

@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: int):
    await websocket.accept()
    connections[player_id] = websocket
    print(f"✅ 玩家 {player_id} 已连接")

    try:
        while True:
            data = await websocket.receive_text()
            print(f"📨 收到玩家 {player_id}: {data}")

            if game.phase == GamePhase.DAY_DISCUSSION and game.current_speaker == player_id:
                for conn in connections.values():
                    await conn.send_text(json.dumps({
                        "type": "SPEECH",
                        "data": {"player_id": player_id, "content": data}
                    }))
                next_speaker = game.next_speaker()
                if next_speaker:
                    for conn in connections.values():
                        await conn.send_text(json.dumps({
                            "type": "NEXT_SPEAKER",
                            "data": {"speaker": next_speaker}
                        }))
                elif game.phase == GamePhase.DAY_VOTE:
                    for conn in connections.values():
                        await conn.send_text(json.dumps({
                            "type": "VOTE_PHASE",
                            "data": {"message": "Now voting time!"}
                        }))

            await websocket.send_text(json.dumps({"type": "ACK", "data": "received"}))

    except WebSocketDisconnect:
        del connections[player_id]
        print(f"❌ 玩家 {player_id} 断开")
