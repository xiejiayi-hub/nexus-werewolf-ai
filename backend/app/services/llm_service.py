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

# 根据模式设置实际 URL
if USE_MODE == "proxy":
    API_URL = PROXY_URL
else:
    API_URL = DIRECT_URL

TIMEOUT_SECONDS = 10
MAX_RETRIES = 2
RETRY_DELAY = 1
# ============================


def _get_speech_prompt(role: str, game_state: str, history: str) -> str:
    """生成发言 - 活人模仿模式"""
    
    role_names = {
        "WEREWOLF": "狼人",
        "SEER": "预言家", 
        "VILLAGER": "平民"
    }
    
    return f"""你是一个真实的人类玩家，正在玩狼人杀。你的身份是{role_names.get(role, '平民')}。

不要像AI那样说话，要像一个真人：
- 说话要有情绪（怀疑、无奈、激动、忽悠）
- 可以用口语词：'我觉得'、'感觉'、'反正'、'其实就是'、'不是我说'
- 可以反问别人：'你倒是说说看？'、'你什么意思？'
- 可以给自己找理由：'我就是一个平民'、'我说的是真的'
- 可以带节奏：'投票吧'、'我跟你'、'听我的'

请模仿真人，不要像AI一样说"我是平民，过"这种话。

直接说你要说的话（一句话就行），不要加引号："""


def _get_thought_prompt(role: str, game_state: str, history: str) -> str:
    """生成内心独白 - 活人思考模式"""
    
    role_names = {
        "WEREWOLF": "狼人",
        "SEER": "预言家", 
        "VILLAGER": "平民"
    }
    
    return f"""你是一个真实的人类玩家，正在玩狼人杀。你的身份是{role_names.get(role, '平民')}。

这是你的内心独白（不会公开），请说出你此刻的真实想法：
- 你怀疑谁？为什么？
- 你相信谁？
- 如果你是狼人，你在想什么战术？
- 如果你是预言家，你在想要不要跳？

直接说出你的想法（一句话就行），不要加引号："""


def _get_trust_prompt(role: str, history: str, speech: str) -> str:
    """生成信任值评估的 Prompt"""
    return f"""你是狼人杀中的【{role}】。根据以下发言，评估每个玩家的可信度（0-100分）。

历史对话：{history}
最新发言：{speech}

请只返回 JSON 格式：{{"1": 50, "2": 50, "3": 50, "4": 50, "5": 50, "6": 50}}"""


def _call_api_with_retry(prompt: str, max_retries: int = MAX_RETRIES) -> Optional[str]:
    """带重试的 API 调用"""
    headers = {"Content-Type": "application/json"}
    
    # 如果是直连模式，添加 Authorization
    if USE_MODE == "direct" and DEEPSEEK_API_KEY:
        headers["Authorization"] = f"Bearer {DEEPSEEK_API_KEY}"
    
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 150,
        "temperature": 0.8  # 提高温度让回答更多样
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
                    return result
            else:
                print(f"API 返回错误码: {resp.status_code}, 响应: {resp.text[:200]}")
        except requests.Timeout:
            print(f"API 超时 (尝试 {attempt + 1}/{max_retries})")
        except Exception as e:
            print(f"API 错误: {e}")
        
        if attempt < max_retries - 1:
            import time
            time.sleep(RETRY_DELAY)
    
    return None


def _get_fallback_response(role: str) -> Dict[str, Any]:
    """降级发言（API 超时或失败时使用）"""
    fallback_speeches = {
        "WEREWOLF": ["我觉得3号有问题", "先观察一下", "我跟预言家走"],
        "SEER": ["我觉得2号是好人", "3号有点可疑", "先听听别人"],
        "VILLAGER": ["没信息，过", "听预言家的", "我跟票"]
    }
    
    fallback_thoughts = {
        "WEREWOLF": ["隐藏身份", "装好人", "别被识破"],
        "SEER": ["先不跳", "再观察", "找狼人中"],
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
    """解析 JSON 响应"""
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
    """获取 AI 回复（带超时控制和降级发言）"""
    
    # 1. 生成公开发言
    speech_prompt = _get_speech_prompt(role, game_state, history)
    speech = await asyncio.to_thread(_call_api_with_retry, speech_prompt)
    
    # 2. 生成内心独白
    thought_prompt = _get_thought_prompt(role, game_state, history)
    thought = await asyncio.to_thread(_call_api_with_retry, thought_prompt)
    
    # 3. 如果 API 失败，使用降级发言
    fallback_used = False
    if not speech or not thought:
        fallback = _get_fallback_response(role)
        if not speech:
            speech = fallback["speech"]
        if not thought:
            thought = fallback["thought"]
        fallback_used = True
    
    # 4. 生成信任值
    trust_prompt = _get_trust_prompt(role, history, speech)
    trust_response = await asyncio.to_thread(_call_api_with_retry, trust_prompt)
    trust_scores = {}
    
    if trust_response:
        parsed = _parse_json_response(trust_response)
        if parsed:
            trust_scores = {k: min(100, max(0, int(v))) for k, v in parsed.items()}
    
    # 5. 如果信任值解析失败，生成默认值
    if not trust_scores:
        trust_scores = {str(i): 50 for i in range(1, 7)}
    
    # 6. 确保信任值包含自己（自己对自己100分）
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
    """带超时控制的 AI 回复"""
    try:
        return await asyncio.wait_for(
            get_ai_response(player_id, role, game_state, history),
            timeout=timeout + 5
        )
    except asyncio.TimeoutError:
        print(f"AI 调用整体超时，使用降级发言")
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
    """同步测试函数"""
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