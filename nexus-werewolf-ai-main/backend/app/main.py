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

    first_speaker = game.start_day_phase()

    return {
        "message": "Game started",
        "phase": game.phase,
        "first_speaker": first_speaker,
        "roles": {str(k): v for k, v in roles.items()}
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

    return {"status": "voted", "votes": game.votes}

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

            await websocket.send_text(json.dumps({"type": "ACK", "data": "received"}))

    except WebSocketDisconnect:
        del connections[player_id]
        print(f"❌ 玩家 {player_id} 断开")
