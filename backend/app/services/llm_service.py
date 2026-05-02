# backend/app/services/llm_service.py

import requests
import json
import asyncio
import random
from typing import Dict, Any, Optional
from datetime import datetime

API_URL = "http://localhost:6006/v1/chat/completions"
MODEL_PATH = "/root/autodl-tmp/DeepSeek-R1-Distill-Qwen-7B"

# 配置
TIMEOUT_SECONDS = 10
MAX_RETRIES = 2
RETRY_DELAY = 1


def _get_speech_prompt(role: str, game_state: str, history: str) -> str:
    """生成公开发言的 Prompt"""
    prompts = {
        "WEREWOLF": f"你是狼人杀中的【狼人】。你的目标是隐藏身份，迷惑好人。状态：{game_state}，历史：{history}。请用一句话公开说话（不要暴露身份）：",
        "SEER": f"你是狼人杀中的【预言家】。你的目标是找出狼人。状态：{game_state}，历史：{history}。请用一句话公开说话：",
        "VILLAGER": f"你是狼人杀中的【平民】。你的目标是找出狼人。状态：{game_state}，历史：{history}。请用一句话公开说话："
    }
    return prompts.get(role, prompts["VILLAGER"])


def _get_thought_prompt(role: str, game_state: str, history: str) -> str:
    """生成内心独白的 Prompt"""
    return f"你是狼人杀中的【{role}】。状态：{game_state}，历史：{history}。请用一句话说出你的真实想法（不公开，只给自己看）："


def _get_trust_prompt(role: str, history: str, speech: str) -> str:
    """生成信任值评估的 Prompt"""
    return f"""你是狼人杀中的【{role}】。根据以下发言，评估每个玩家的可信度（0-100分）。

历史对话：{history}
最新发言：{speech}

请只返回 JSON 格式：{{"1": 50, "2": 50, "3": 50, "4": 50, "5": 50, "6": 50}}"""


def _call_api_with_retry(prompt: str, max_retries: int = MAX_RETRIES) -> Optional[str]:
    """带重试的 API 调用"""
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                API_URL,
                headers={"Content-Type": "application/json"},
                json={
                    "model": MODEL_PATH,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.7
                },
                timeout=TIMEOUT_SECONDS
            )
            if resp.status_code == 200:
                result = resp.json()["choices"][0]["message"]["content"].strip()
                if result:
                    return result
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
        "WEREWOLF": ["我是好人，过", "我感觉3号有问题", "先观察一下"],
        "SEER": ["我是平民，过", "暂时没信息", "先听听别人"],
        "VILLAGER": ["我是平民，过", "没信息，过", "听预言家的"]
    }
    
    fallback_thoughts = {
        "WEREWOLF": ["别暴露，装好人", "隐藏身份", "跟着好人投票"],
        "SEER": ["先不跳，观察一下", "找个时机跳预言家", "保护好自己"],
        "VILLAGER": ["跟着感觉走", "观察发言漏洞", "找狼人"]
    }
    
    speeches = fallback_speeches.get(role, fallback_speeches["VILLAGER"])
    thoughts = fallback_thoughts.get(role, fallback_thoughts["VILLAGER"])
    
    return {
        "thought": random.choice(thoughts) + "（API超时，降级发言）",
        "speech": random.choice(speeches),
        "fallback": True
    }


def _parse_json_response(response: str) -> Optional[Dict]:
    """解析 JSON 响应"""
    try:
        # 尝试直接解析
        return json.loads(response)
    except:
        # 尝试提取 JSON 部分
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
    """
    获取 AI 回复（带超时控制和降级发言）
    
    返回格式符合协议：
    {
        "player_id": int,
        "role": str,
        "thought": str,
        "speech": str,
        "vote_target": Optional[int],
        "trust_scores": Dict[str, int]
    }
    """
    
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
    
    # 7. 返回结果
    return {
        "player_id": player_id,
        "role": role,
        "thought": thought,
        "speech": speech,
        "vote_target": None,  # 由投票阶段决定
        "trust_scores": trust_scores,
        "_meta": {"fallback": fallback_used}  # 调试信息
    }


async def get_ai_response_with_timeout(
    player_id: int,
    role: str,
    game_state: str,
    history: str,
    timeout: int = TIMEOUT_SECONDS
) -> Dict[str, Any]:
    """
    带超时控制的 AI 回复（外层包装）
    确保整个调用过程不超过 timeout 秒
    """
    try:
        return await asyncio.wait_for(
            get_ai_response(player_id, role, game_state, history),
            timeout=timeout + 5  # 给内部重试留时间
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


# 同步版本的测试函数（方便直接运行测试）
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
    # 运行测试
    test_sync()