import requests
import json
from typing import Dict, Any

API_URL = "http://localhost:6006/v1/chat/completions"
MODEL_PATH = "/root/autodl-tmp/DeepSeek-R1-Distill-Qwen-7B"

async def get_ai_response(player_id: int, role: str, game_state: str, history: str) -> Dict[str, Any]:
    # 简单 Prompt
    prompt = f"""你是狼人杀游戏中的【{role}】。
当前状态：{game_state}
历史：{history}

请用一句话发言："""
    
    try:
        resp = requests.post(API_URL, headers={"Content-Type": "application/json"},
            json={"model": MODEL_PATH, "messages": [{"role": "user", "content": prompt}], "max_tokens": 200, "temperature": 0.7})
        if resp.status_code == 200:
            speech = resp.json()["choices"][0]["message"]["content"].strip()
        else:
            speech = "我是平民，过"
    except Exception as e:
        print(f"API调用错误: {e}")
        speech = "我是平民，过"
    
    # thought 取 speech 的前 100 字
    thought = speech[:100] if len(speech) > 100 else speech
    
    # trust_scores 默认所有玩家 50
    trust_scores = {str(i): 50 for i in range(1, 7)}
    
    return {
        "player_id": player_id,
        "role": role,
        "thought": thought,
        "speech": speech,
        "vote_target": None,
        "trust_scores": trust_scores
    }
