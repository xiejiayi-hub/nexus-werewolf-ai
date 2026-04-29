import requests
BASE_URL = "http://localhost:8000"

def test_game_full_flow():
    # 创建房间
    room = requests.post(f"{BASE_URL}/api/v1/room/create", json={"player_num": 6}).json()
    room_id = room["data"]["room_id"]

    # 加入玩家
    requests.post(f"{BASE_URL}/api/v1/player/join", json={"room_id": room_id, "player_name": "测试玩家"})

    # 开始游戏
    res = requests.post(f"{BASE_URL}/api/v1/game/start", json={"room_id": room_id})
    assert res.status_code == 200

    # 夜晚
    res = requests.post(f"{BASE_URL}/api/v1/game/night", json={"room_id": room_id})
    assert res.status_code == 200