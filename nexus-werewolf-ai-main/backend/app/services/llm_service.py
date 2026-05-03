import requests
import json
import re
from typing import Dict, Any

API_URL = "https://api.deepseek.com/v1/chat/completions"
API_KEY = "sk-b8f0354beca6443eb6dbf96e48ab4608"
MODEL_NAME = "deepseek-chat"

def parse_trust_scores(text: str) -> dict:
    """从 AI 回复中解析信任值"""
    match = re.search(r'【信任】[：:]\s*(.+?)(?=$|【)', text, re.DOTALL)
    if match:
        scores_str = match.group(1)
        pairs = re.findall(r'玩家(\d+)[=:：](\d+)', scores_str)
        if pairs:
            return {str(p): int(s) for p, s in pairs}
    return {str(i): 50 for i in range(1, 7)}

async def get_ai_response(player_id: int, role: str, game_state: str, history: str) -> Dict[str, Any]:
    prompt = f"""你是狼人杀游戏中的【{role}】。
当前状态：{game_state}
历史：{history}

请按以下格式输出：
【发言】：你的发言内容
【信任】：玩家1=数值,玩家2=数值,玩家3=数值,玩家4=数值,玩家5=数值,玩家6=数值

信任值范围 0-100，100 表示完全信任，0 表示完全不信任。
"""
    
    if role == "WEREWOLF":
        prompt += " 你是狼人，需要隐藏身份。可以说谎，比如假装自己是平民或预言家。"
    
    try:
        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "max_tokens": 300, "temperature": 0.7}
        )
        if resp.status_code == 200:
            resp_text = resp.json()["choices"][0]["message"]["content"].strip()
        else:
            resp_text = "我是平民，过"
    except Exception as e:
        print(f"API调用错误: {e}")
        resp_text = "我是平民，过"
    
    speech_match = re.search(r'【发言】[：:]\s*(.+?)(?=$|【)', resp_text, re.DOTALL)
    speech = speech_match.group(1).strip() if speech_match else resp_text[:200]
    trust_scores = parse_trust_scores(resp_text)
    thought = speech[:100] if len(speech) > 100 else speech
    
    return {
        "player_id": player_id,
        "role": role,
        "thought": thought,
        "speech": speech,
        "vote_target": None,
        "trust_scores": trust_scores
    }