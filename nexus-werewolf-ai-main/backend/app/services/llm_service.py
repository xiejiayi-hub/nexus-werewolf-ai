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

def _get_trust_prompt(role: str, game_state: str, history: str) -> str:
    """生成信任评分 Prompt（文档要求的函数名）"""
    prompt = f"""你是狼人杀游戏中的【{role}】。

当前状态：{game_state}
历史发言：{history}

【严格要求】你必须且只能按以下格式输出，不能缺任何一个玩家：

【发言】：（你的发言内容，一句话）
【信任】：玩家1=数值,玩家2=数值,玩家3=数值,玩家4=数值,玩家5=数值,玩家6=数值

信任值规则：
- 100 = 完全信任（确定是好人）
- 80-99 = 非常信任
- 60-79 = 比较信任
- 40-59 = 中性/不确定
- 20-39 = 有点怀疑
- 0-19 = 非常怀疑（很可能是狼人）

【重要】你必须对每个玩家都给出信任值，不能全部给 50。根据发言内容和逻辑判断。

现在请输出："""
    
    if role == "WEREWOLF":
        prompt += "\n（你是狼人，请假装自己是好人发言，隐藏身份。）"
    
    return prompt

async def get_ai_response(player_id: int, role: str, game_state: str, history: str) -> Dict[str, Any]:
    # 使用文档要求的函数生成 Prompt
    prompt = _get_trust_prompt(role, game_state, history)
    
    try:
        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 400,
                "temperature": 0.8
            },
            timeout=15
        )
        if resp.status_code == 200:
            resp_text = resp.json()["choices"][0]["message"]["content"].strip()
        else:
            resp_text = ""
    except Exception as e:
        print(f"API调用错误: {e}")
        resp_text = ""
    
    if not resp_text:
        resp_text = "【发言】：我是平民，过。\n【信任】：玩家1=50,玩家2=50,玩家3=50,玩家4=50,玩家5=50,玩家6=50"
    
    # 解析发言
    speech_match = re.search(r'【发言】[：:]\s*(.+?)(?=$|【)', resp_text, re.DOTALL)
    speech = speech_match.group(1).strip() if speech_match else "我是平民，过"
    
    # 解析信任值
    trust_scores = parse_trust_scores(resp_text)
    
    # 确保所有玩家都有信任值
    for i in range(1, 7):
        if str(i) not in trust_scores:
            trust_scores[str(i)] = 50
    
    # 内心想法（取发言前100字）
    thought = speech[:100] if len(speech) > 100 else speech
    
    return {
        "player_id": player_id,
        "role": role,
        "thought": thought,
        "speech": speech,
        "vote_target": None,
        "trust_scores": trust_scores
    }