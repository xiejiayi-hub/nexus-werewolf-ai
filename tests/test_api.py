import requests
BASE_URL = "http://localhost:8000"

def test_server_alive():
    try:
        res = requests.get(BASE_URL, timeout=3)
        assert res.status_code in (200, 404)
    except:
        assert False, "后端未启动！"

def test_create_room():
    res = requests.post(f"{BASE_URL}/api/game/start", json={"player_num": 6})
    assert res.status_code == 200
    data = res.json()
    assert "data" in data
    assert "room_id" in data["data"]