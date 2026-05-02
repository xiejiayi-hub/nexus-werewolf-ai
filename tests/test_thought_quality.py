# tests/test_thought_quality.py
import json
import pytest

# 模拟AI返回的JSON（实际用你的API代理调用）
def mock_ai_response():
    return {
        "thought": "我怀疑3号玩家发言有漏洞，大概率是狼人，接下来我会观察他的投票行为来验证",
        "target": 3,
        "action": "accuse"
    }

def test_thought_field_exists():
    """测试响应中是否包含thought字段"""
    resp = mock_ai_response()
    assert "thought" in resp, "响应缺少thought字段"

def test_thought_not_empty():
    """测试thought内容不为空"""
    resp = mock_ai_response()
    thought = resp["thought"].strip()
    assert len(thought) > 5, "thought内容过短或为空"

def test_thought_contains_keywords():
    """测试thought包含狼人杀相关逻辑关键词"""
    resp = mock_ai_response()
    thought = resp["thought"].lower()
    keywords = ["怀疑", "信任", "策略", "发言", "投票", "身份", "狼人", "预言家"]
    has_keyword = any(kw in thought for kw in keywords)
    assert has_keyword, "thought内容无有效逻辑，未包含关键信息"

def test_response_json_valid():
    """测试返回的JSON格式合法"""
    try:
        json.dumps(mock_ai_response())
    except Exception as e:
        pytest.fail(f"JSON格式错误: {e}")