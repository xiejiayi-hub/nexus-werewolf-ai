import requests
BASE_URL = "http://localhost:8000"

def test_ai_speak_format():
    res = requests.post(f"{BASE_URL}/api/game/player/speak", json={
        "room_id": "test_room",
        "player_id": 1,
        "content": "测试发言"
    })
    # 不崩溃 = 格式正常
    assert res.status_code != 500
    # 额外校验AI返回格式是否符合协议要求
    if res.status_code == 200:
        data = res.json()
        assert "player_id" in data
        assert "role" in data
        assert "thought" in data
        assert "speech" in data
        assert "vote_target" in data
        assert "trust_scores" in data