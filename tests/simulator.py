# 自动化对战测试脚本（狼人杀AI 6人模拟）
# 你（E：工程/QA）Day2 任务

import requests
import time

# 后端地址
BASE_URL = "http://localhost:8000"

def main():
    print("=== 开始自动化狼人杀6人对战模拟 ===")

    # 1. 创建房间
    print("\n1. 创建房间...")
    room = requests.post(f"{BASE_URL}/api/v1/room/create", json={
        "player_num": 6
    }).json()
    room_id = room["data"]["room_id"]
    print(f"房间创建成功：{room_id}")

    # 2. 6个玩家加入房间
    players = []
    print("\n2. 6个玩家加入房间...")
    for i in range(1, 7):
        res = requests.post(f"{BASE_URL}/api/v1/player/join", json={
            "room_id": room_id,
            "player_name": f"AI玩家{i}"
        }).json()
        player_id = res["data"]["player_id"]
        players.append(player_id)
        print(f"玩家{i} 加入，ID：{player_id}")

    # 3. 开始游戏
    print("\n3. 启动游戏...")
    requests.post(f"{BASE_URL}/api/v1/game/start", json={
        "room_id": room_id
    })

    # 4. 循环游戏流程
    print("\n4. 开始游戏循环（天黑→发言→投票）")
    for round_num in range(3):
        print(f"\n===== 第 {round_num+1} 轮 =====")

        # 夜晚：狼人杀人
        print("[夜晚] 狼人执行杀人...")
        requests.post(f"{BASE_URL}/api/v1/game/night", json={
            "room_id": room_id
        })
        time.sleep(1)

        # 白天：所有玩家发言
        print("[白天] 所有玩家发言...")
        for pid in players:
            requests.post(f"{BASE_URL}/api/v1/player/speak", json={
                "room_id": room_id,
                "player_id": pid,
                "content": "我是好人，跟着大家投票。"
            })
            time.sleep(0.3)

        # 投票阶段
        print("[投票] 开始放逐投票...")
        for pid in players:
            requests.post(f"{BASE_URL}/api/v1/player/vote", json={
                "room_id": room_id,
                "player_id": pid,
                "target_id": players[0]  # 随便投一个
            })
        time.sleep(1)

    print("\n=== 自动化对战测试完成 ===")

if __name__ == "__main__":
    main()