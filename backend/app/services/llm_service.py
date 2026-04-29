# backend/app/services/llm_service.py

import requests
import json
from typing import Dict, Any

API_URL = "http://localhost:6006/v1/chat/completions"
MODEL_PATH = "/root/autodl-tmp/DeepSeek-R1-Distill-Qwen-7B"

def _get_speech_prompt(role: str, game_state: str, history: str) -> str:
    prompts = {
        "WEREWOLF": f"你是狼人杀中的【狼人】。状态：{game_state}，历史：{history}。用一句话公开说话：",
        "SEER": f"你是狼人杀中的【预言家】。状态：{game_state}，历史：{history}。用一句话公开说话：",
        "VILLAGER": f"你是狼人杀中的【平民】。状态：{game_state}，历史：{history}。用一句话公开说话："
    }
    return prompts.get(role, prompts["VILLAGER"])

def _get_thought_prompt(role: str, game_state: str, history: str) -> str:
    return f"你是狼人杀中的【{role}】。状态：{game_state}，历史：{history}。用一句话说你的真实想法（不是公开说话）："

def _call_api(prompt: str) -> str:
    try:
        resp = requests.post(API_URL, headers={"Content-Type": "application/json"},
            json={"model": MODEL_PATH, "messages": [{"role": "user", "content": prompt}], "max_tokens": 100})
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
    except:
        pass
    return ""

async def get_ai_response(player_id: int, role: str, game_state: str, history: str) -> Dict[str, Any]:
    speech = _call_api(_get_speech_prompt(role, game_state, history))
    thought = _call_api(_get_thought_prompt(role, game_state, history))
    return {
        "player_id": player_id,
        "role": role,
        "thought": thought or "思考中",
        "speech": speech or "我是平民，过",
        "vote_target": None,
        "trust_scores": {}
    }