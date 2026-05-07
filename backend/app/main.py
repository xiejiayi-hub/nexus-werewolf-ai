from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
from dotenv import load_dotenv
from app.core.game_state import GameStateMachine, GamePhase

load_dotenv()

# =====================
# 状态
# =====================
connections = {}   # {player_id: websocket}
ai_thoughts = {}

game = GameStateMachine()
human_player_id = 1


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
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================
# 工具函数（稳定版广播）
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
# API
# =====================
@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/ai/thought/{player_id}")
async def get_thought(player_id: int):
    return {
        "player_id": player_id,
        "thought": ai_thoughts.get(player_id, "暂无思考记录")
    }


@app.get("/api/game/status")
async def status():
    return {
        "current_speaker": game.current_speaker,
        "phase": str(game.phase),
        "alive_players": game.alive_players
    }


@app.get("/api/game/trust-matrix")
async def trust_matrix():
    return {
        "trust_matrix": {
            str(i): {str(j): 50 for j in range(1, 7) if i != j}
            for i in range(1, 7)
        }
    }


@app.post("/api/game/start")
async def start_game():
    player_ids = [1, 2, 3, 4, 5, 6]

    game.assign_roles(player_ids)
    game.start_day_phase()

    await broadcast({
        "type": "GAME_START",
        "data": {
            "first_speaker": game.current_speaker
        }
    })

    return {
        "status": "ok",
        "first_speaker": game.current_speaker
    }


# =====================
# WebSocket（稳定版）
# =====================
@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: int):
    await websocket.accept()
    connections[player_id] = websocket

    print(f"玩家 {player_id} 已连接")

    try:
        while True:
            data = await websocket.receive_text()

            print(f"[{player_id}] {data}")

            # 1. 广播发言（仅广播，不改游戏状态）
            await broadcast({
                "type": "SPEECH",
                "data": {
                    "player_id": player_id,
                    "content": data
                }
            })

            # ❗关键修正：不再自动切换玩家
            # game.next_speaker() 交给 API 或按钮控制

    except WebSocketDisconnect:
        connections.pop(player_id, None)
        print(f"玩家 {player_id} 断开")