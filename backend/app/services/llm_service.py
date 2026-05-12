# backend/app/services/llm_service.py

import requests
import json
import asyncio
import random
import os
from typing import Dict, Any, Optional
from datetime import datetime

# ========== 配置区域 ==========
PROXY_URL = "http://10.41.0.180:8001/deepseek/v1/chat/completions"
DIRECT_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = "sk-b8f0354beca6443eb6dbf96e48ab4608"
USE_MODE = "direct"

if USE_MODE == "proxy":
    API_URL = PROXY_URL
else:
    API_URL = DIRECT_URL

TIMEOUT_SECONDS = 10
MAX_RETRIES = 2
RETRY_DELAY = 1

# 随机开头词库
SPEECH_STARTERS = [
    "我觉得", "我感觉", "我怀疑", "说实话", "讲道理",
    "那个", "嗯", "好吧", "有一说一", "反正",
    "我", "听我说", "各位", "我认为", "其实"
]
# ============================


def _get_speech_prompt(role: str, game_state: str, history: str) -> str:
    """生成发言 - 多样化开头"""
    
    role_names = {
        "WEREWOLF": "狼人",
        "SEER": "预言家",
        "GUARDIAN": "守卫",
        "VILLAGER": "平民"
    }
    
    starter = random.choice(SPEECH_STARTERS)
    
    return f"""你是狼人杀中的【{role_names.get(role, '平民')}】。
请以「{starter}」开头说一句话。

游戏状态：{game_state}
历史发言：{history}

直接说你要说的话（一句话，自然口语，不要以「不是」开头）："""


def _get_thought_prompt(role: str, game_state: str, history: str) -> str:
    """生成内心独白 - 多样化"""
    
    role_names = {
        "WEREWOLF": "狼人",
        "SEER": "预言家",
        "GUARDIAN": "守卫",
        "VILLAGER": "平民"
    }
    
    return f"""你是狼人杀中的【{role_names.get(role, '平民')}】。

这是你的内心独白，请说出你的真实想法（一句话）：
- 你怀疑谁？为什么？
- 你相信谁？
- 你的策略是什么？

游戏状态：{game_state}
历史发言：{history}

内心独白："""


def _get_trust_prompt(role: str, history: str, speech: str) -> str:
    """生成信任值评估的 Prompt"""
    return f"""你是狼人杀中的【{role}】。根据发言给其他玩家打分（0-100分）。

规则：
- 80以上：很可能是好人
- 60-80：比较可信
- 40-60：中性
- 20-40：有点可疑
- 20以下：很像狼人

历史对话：{history}
最新发言：{speech}

只返回 JSON，例如：{{"2": 60, "3": 30, "4": 70, "5": 50, "6": 40}}"""


def _call_api_with_retry(prompt: str, max_retries: int = MAX_RETRIES) -> Optional[str]:
    headers = {"Content-Type": "application/json"}
    
    if USE_MODE == "direct" and DEEPSEEK_API_KEY:
        headers["Authorization"] = f"Bearer {DEEPSEEK_API_KEY}"
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 80,
        "temperature": 0.9
    }
    
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=TIMEOUT_SECONDS
            )
            if resp.status_code == 200:
                result = resp.json()["choices"][0]["message"]["content"].strip()
                if result:
                    # 清理常见问题
                    result = result.replace('"', '').strip()
                    return result
            else:
                print(f"API 返回错误码: {resp.status_code}")
        except requests.Timeout:
            print(f"API 超时 (尝试 {attempt + 1}/{max_retries})")
        except Exception as e:
            print(f"API 错误: {e}")
        
        if attempt < max_retries - 1:
            import time
            time.sleep(RETRY_DELAY)
    
    return None


def _get_fallback_response(role: str) -> Dict[str, Any]:
    fallback_speeches = {
        "WEREWOLF": ["我觉得3号有问题", "先观察一下", "我跟预言家走"],
        "SEER": ["我觉得2号是好人", "3号有点可疑", "先听听别人"],
        "GUARDIAN": ["我是平民，过", "跟预言家走", "过"],
        "VILLAGER": ["没信息，过", "听预言家的", "我跟票"]
    }
    
    fallback_thoughts = {
        "WEREWOLF": ["隐藏身份", "装好人", "别被识破"],
        "SEER": ["先不跳", "再观察", "找狼人中"],
        "GUARDIAN": ["我是守卫，保护好预言家", "今晚守谁呢", "低调"],
        "VILLAGER": ["跟着感觉走", "观察发言", "找狼人"]
    }
    
    speeches = fallback_speeches.get(role, fallback_speeches["VILLAGER"])
    thoughts = fallback_thoughts.get(role, fallback_thoughts["VILLAGER"])
    
    return {
        "thought": random.choice(thoughts) + "（API超时）",
        "speech": random.choice(speeches),
        "fallback": True
    }


def _parse_json_response(response: str) -> Optional[Dict]:
    try:
        return json.loads(response)
    except:
        import re
        json_match = re.search(r'\{[^{}]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass
    return None


async def get_ai_response(
    player_id: int, 
    role: str, 
    game_state: str, 
    history: str,
    timeout: int = TIMEOUT_SECONDS
) -> Dict[str, Any]:
    
    speech_prompt = _get_speech_prompt(role, game_state, history)
    speech = await asyncio.to_thread(_call_api_with_retry, speech_prompt)
    
    thought_prompt = _get_thought_prompt(role, game_state, history)
    thought = await asyncio.to_thread(_call_api_with_retry, thought_prompt)
    
    fallback_used = False
    if not speech or not thought:
        fallback = _get_fallback_response(role)
        if not speech:
            speech = fallback["speech"]
        if not thought:
            thought = fallback["thought"]
        fallback_used = True
    
    trust_prompt = _get_trust_prompt(role, history, speech)
    trust_response = await asyncio.to_thread(_call_api_with_retry, trust_prompt)
    trust_scores = {}
    
    if trust_response:
        parsed = _parse_json_response(trust_response)
        if parsed:
            trust_scores = {k: min(100, max(0, int(v))) for k, v in parsed.items()}
    
    if not trust_scores:
        trust_scores = {str(i): 50 for i in range(1, 7)}
    
    trust_scores[str(player_id)] = 100
    
    return {
        "player_id": player_id,
        "role": role,
        "thought": thought,
        "speech": speech,
        "vote_target": None,
        "trust_scores": trust_scores,
        "_meta": {"fallback": fallback_used}
    }


async def get_ai_response_with_timeout(
    player_id: int,
    role: str,
    game_state: str,
    history: str,
    timeout: int = TIMEOUT_SECONDS
) -> Dict[str, Any]:
    try:
        return await asyncio.wait_for(
            get_ai_response(player_id, role, game_state, history),
            timeout=timeout + 5
        )
    except asyncio.TimeoutError:
        print(f"AI 调用整体超时")
        fallback = _get_fallback_response(role)
        return {
            "player_id": player_id,
            "role": role,
            "thought": fallback["thought"] + "（全局超时）",
            "speech": fallback["speech"],
            "vote_target": None,
            "trust_scores": {str(i): 50 for i in range(1, 7)},
            "_meta": {"fallback": True, "timeout": True}
        }


def test_sync(player_id: int = 1, role: str = "VILLAGER"):
    import asyncio
    result = asyncio.run(get_ai_response_with_timeout(
        player_id=player_id,
        role=role,
        game_state="第1天白天，所有玩家存活",
        history="无历史"
    ))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    test_sync()