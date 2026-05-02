from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import os
from dotenv import load_dotenv
from app.core.game_state import GameStateMachine, Role, GamePhase

load_dotenv()

game = GameStateMachine()
human_player_id = 1

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("服务器启动成功")
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
ai_thoughts = {}

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
        "human_player": human_player_id,
        "roles": {str(k): v for k, v in roles.items()}
    }

@app.post("/api/game/ai/speak")
async def ai_speak(player_id: int, speech: str, thought: str, vote_target: int):
    ai_thoughts[player_id] = thought
    
    for conn in connections.values():
        await conn.send_text(json.dumps({
            "type": "AI_SPEECH",
            "data": {
                "player_id": player_id,
                "speech": speech,
                "thought": thought
            }
        }))
    
    if game.phase == GamePhase.DAY_VOTE:
        game.record_vote(player_id, vote_target)
    
    if game.phase == GamePhase.DAY_DISCUSSION:
        next_speaker = game.next_speaker()
        if next_speaker:
            if next_speaker == human_player_id:
                for conn in connections.values():
                    await conn.send_text(json.dumps({
                        "type": "YOUR_TURN",
                        "data": {"message": "轮到你了", "time_limit": 30}
                    }))
            else:
                for conn in connections.values():
                    await conn.send_text(json.dumps({
                        "type": "NEXT_SPEAKER",
                        "data": {"speaker": next_speaker}
                    }))
    
    return {"status": "ok"}

@app.get("/api/game/trust-matrix")
async def get_trust_matrix():
    sample_matrix = {}
    for i in range(1, 7):
        sample_matrix[str(i)] = {}
        for j in range(1, 7):
            if i != j:
                sample_matrix[str(i)][str(j)] = 50
    return {"trust_matrix": sample_matrix}

@app.post("/api/game/night/wolf")
async def wolf_vote(wolf_id: int, target_id: int):
    if game.phase != GamePhase.NIGHT_WOLF:
        return {"error": "Not in wolf night phase"}
    
    game.record_wolf_vote(wolf_id, target_id)
    
    werewolves = [p for p in game.players if p["role"] == Role.WEREWOLF and p["alive"]]
    if len(game.wolf_votes) == len(werewolves):
        killed = game.resolve_wolf_kill()
        game.phase = GamePhase.NIGHT_SEER
        return {"status": "votes recorded", "killed": killed, "next_phase": "NIGHT_SEER"}
    
    return {"status": "vote recorded"}

@app.post("/api/game/night/seer")
async def seer_check(target_id: int):
    if game.phase != GamePhase.NIGHT_SEER:
        return {"error": "Not in seer night phase"}
    
    game.record_seer_check(target_id)
    result = game.get_seer_result()
    
    killed = game.resolve_night()
    
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
            
            if game.phase == GamePhase.GAME_OVER:
                winner = game.get_winner()
                for conn in connections.values():
                    await conn.send_text(json.dumps({
                        "type": "GAME_OVER",
                        "data": {"winner": winner}
                    }))
        else:
            game.start_night_phase()

    return {"status": "voted", "votes": game.votes}

# backend/app/main.py - 完整版本

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import os
import asyncio
from dotenv import load_dotenv
from app.core.game_state import GameStateMachine, Role, GamePhase

load_dotenv()

game = GameStateMachine()
human_player_id = 1
current_timeout_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("服务器启动成功")
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
ai_thoughts = {}


async def human_timeout_task(player_id: int, speech_timeout: int = 30):
    """人类玩家超时未发言，自动跳过"""
    await asyncio.sleep(speech_timeout)
    
    if game.current_speaker == player_id and game.phase == GamePhase.DAY_DISCUSSION:
        print(f"⏰ 人类玩家 {player_id} 超时未发言，自动跳过")
        
        for conn in connections.values():
            await conn.send_text(json.dumps({
                "type": "TIMEOUT",
                "data": {"player_id": player_id, "message": "发言超时，自动跳过"}
            }))
        
        next_speaker = game.next_speaker()
        if next_speaker:
            for conn in connections.values():
                if next_speaker == human_player_id:
                    await conn.send_text(json.dumps({
                        "type": "YOUR_TURN",
                        "data": {"speaker": next_speaker, "time_limit": 30}
                    }))
                    global current_timeout_task
                    current_timeout_task = asyncio.create_task(
                        human_timeout_task(human_player_id, 30)
                    )
                else:
                    await conn.send_text(json.dumps({
                        "type": "NEXT_SPEAKER",
                        "data": {"speaker": next_speaker}
                    }))
        elif game.phase == GamePhase.DAY_VOTE:
            for conn in connections.values():
                await conn.send_text(json.dumps({
                    "type": "VOTE_PHASE",
                    "data": {"message": "发言结束，开始投票"}
                }))


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

    # 如果第一个发言的是人类，发送 YOUR_TURN
    if game.current_speaker == human_player_id:
        for conn in connections.values():
            await conn.send_text(json.dumps({
                "type": "YOUR_TURN",
                "data": {"speaker": game.current_speaker, "time_limit": 30}
            }))
        global current_timeout_task
        current_timeout_task = asyncio.create_task(human_timeout_task(human_player_id, 30))

    return {
        "message": "Game started",
        "phase": game.phase,
        "first_speaker": game.current_speaker,
        "human_player": human_player_id,
        "roles": {str(k): v for k, v in roles.items()}
    }


@app.post("/api/game/ai/speak")
async def ai_speak(player_id: int, speech: str, thought: str, vote_target: int = None):
    global current_timeout_task
    
    ai_thoughts[player_id] = thought
    
    for conn in connections.values():
        await conn.send_text(json.dumps({
            "type": "AI_SPEECH",
            "data": {
                "player_id": player_id,
                "speech": speech,
                "thought": thought
            }
        }))
    
    if game.phase == GamePhase.DAY_VOTE and vote_target:
        game.record_vote(player_id, vote_target)
    
    if game.phase == GamePhase.DAY_DISCUSSION and game.current_speaker == player_id:
        next_speaker = game.next_speaker()
        if next_speaker:
            for conn in connections.values():
                if next_speaker == human_player_id:
                    await conn.send_text(json.dumps({
                        "type": "YOUR_TURN",
                        "data": {"speaker": next_speaker, "time_limit": 30}
                    }))
                    if current_timeout_task:
                        current_timeout_task.cancel()
                    current_timeout_task = asyncio.create_task(
                        human_timeout_task(human_player_id, 30)
                    )
                else:
                    await conn.send_text(json.dumps({
                        "type": "NEXT_SPEAKER",
                        "data": {"speaker": next_speaker}
                    }))
        elif game.phase == GamePhase.DAY_VOTE:
            for conn in connections.values():
                await conn.send_text(json.dumps({
                    "type": "VOTE_PHASE",
                    "data": {"message": "发言结束，开始投票"}
                }))
    
    return {"status": "ok"}


@app.get("/api/game/trust-matrix")
async def get_trust_matrix():
    sample_matrix = {}
    for i in range(1, 7):
        sample_matrix[str(i)] = {}
        for j in range(1, 7):
            if i != j:
                sample_matrix[str(i)][str(j)] = 50
    return {"trust_matrix": sample_matrix}


@app.post("/api/game/night/wolf")
async def wolf_vote(wolf_id: int, target_id: int):
    if game.phase != GamePhase.NIGHT_WOLF:
        return {"error": "Not in wolf night phase"}
    
    game.record_wolf_vote(wolf_id, target_id)
    
    werewolves = [p for p in game.players if p["role"] == Role.WEREWOLF and p["alive"]]
    if len(game.wolf_votes) == len(werewolves):
        killed = game.resolve_wolf_kill()
        game.phase = GamePhase.NIGHT_SEER
        return {"status": "votes recorded", "killed": killed, "next_phase": "NIGHT_SEER"}
    
    return {"status": "vote recorded"}


@app.post("/api/game/night/seer")
async def seer_check(target_id: int):
    if game.phase != GamePhase.NIGHT_SEER:
        return {"error": "Not in seer night phase"}
    
    game.record_seer_check(target_id)
    result = game.get_seer_result()
    
    killed = game.resolve_night()
    
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
            
            if game.phase == GamePhase.GAME_OVER:
                winner = game.get_winner()
                for conn in connections.values():
                    await conn.send_text(json.dumps({
                        "type": "GAME_OVER",
                        "data": {"winner": winner}
                    }))
        else:
            game.start_night_phase()

    return {"status": "voted", "votes": game.votes}


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


@app.websocket("/ws/{player_id}")
async def websocket_endpoint(websocket: WebSocket, player_id: int):
    await websocket.accept()
    connections[player_id] = websocket
    print(f"玩家 {player_id} 已连接")
    
    is_human = (player_id == human_player_id)
    global current_timeout_task

    try:
        while True:
            data = await websocket.receive_text()
            print(f"收到玩家 {player_id}: {data}")
            
            if is_human and game.phase == GamePhase.DAY_DISCUSSION:
                if game.current_speaker == human_player_id:
                    if current_timeout_task:
                        current_timeout_task.cancel()
                    
                    for conn in connections.values():
                        await conn.send_text(json.dumps({
                            "type": "SPEECH",
                            "data": {
                                "player_id": human_player_id, 
                                "content": data,
                                "is_human": True
                            }
                        }))
                    
                    next_speaker = game.next_speaker()
                    if next_speaker:
                        for conn in connections.values():
                            if next_speaker == human_player_id:
                                await conn.send_text(json.dumps({
                                    "type": "YOUR_TURN",
                                    "data": {"speaker": next_speaker, "time_limit": 30}
                                }))
                                current_timeout_task = asyncio.create_task(
                                    human_timeout_task(human_player_id, 30)
                                )
                            else:
                                await conn.send_text(json.dumps({
                                    "type": "NEXT_SPEAKER",
                                    "data": {"speaker": next_speaker}
                                }))
                    elif game.phase == GamePhase.DAY_VOTE:
                        for conn in connections.values():
                            await conn.send_text(json.dumps({
                                "type": "VOTE_PHASE",
                                "data": {"message": "发言结束，开始投票"}
                            }))
                else:
                    await websocket.send_text(json.dumps({
                        "type": "ERROR",
                        "data": {"message": "还没轮到你发言"}
                    }))

            await websocket.send_text(json.dumps({"type": "ACK", "data": "received"}))

    except WebSocketDisconnect:
        if current_timeout_task:
            current_timeout_task.cancel()
        del connections[player_id]
        print(f"玩家 {player_id} 断开")