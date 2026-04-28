from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import redis
import json
import os
from dotenv import load_dotenv

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis.Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        decode_responses=True
    )
    app.state.game_state = {
        "players": [],
        "phase": "WAITING",
        "current_speaker": None,
        "round": 0
    }
    print("✅ 服务器启动成功")
    yield
    app.state.redis.close()

app = FastAPI(title="Nexus-Werewolf AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok", "message": "Nexus-Werewolf AI Backend"}

@app.post("/api/game/start")
async def start_game():
    return {"message": "Game started", "phase": "DAY_DISCUSSION"}

@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: int):
    await websocket.accept()
    print(f"✅ 玩家 {player_id} 已连接")
    try:
        while True:
            data = await websocket.receive_text()
            print(f"📨 收到: {data}")
            await websocket.send_text(json.dumps({"type": "ACK", "data": "received"}))
    except WebSocketDisconnect:
        print(f"❌ 玩家 {player_id} 断开")
