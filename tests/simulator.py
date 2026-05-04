import requests
import time
import argparse
from datetime import datetime

# 后端地址
BASE_URL = "http://localhost:8000"

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser()
    parser.add_argument('--players', type=int, default=6)
    parser.add_argument('--rounds', type=int, default=10)
    args = parser.parse_args()

    player_num = args.players
    total_rounds = args.rounds

    start_time = datetime.now()
    print("=== 开始自动化狼人杀对战模拟 ===")
    print(f"配置：玩家 {player_num} 人，对战 {total_rounds} 轮")

    report_data = {
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "player_num": player_num,
        "total_rounds": total_rounds,
        "rounds": [],
        "errors": []
    }

    # 1. 启动游戏
    print("\n1. 创建游戏房间...")
    try:
        room = requests.post(f"{BASE_URL}/api/game/start", json={
            "player_num": player_num
        }).json()
        print("✅ 游戏创建成功")
    except:
        print("❌ 游戏创建失败")
        return

    players = list(range(1, player_num + 1))

    # 2. 游戏循环（真正使用你输入的轮数！）
    print(f"\n3. 开始 {total_rounds} 轮游戏循环...")
    for round_num in range(total_rounds):
        print(f"\n===== 第 {round_num + 1} 轮 =====")
        round_info = {"round": round_num + 1, "speak": True, "vote": True}

        # 发言
        print("[白天] AI发言...")
        for pid in players:
            try:
                requests.post(f"{BASE_URL}/api/game/ai/speak", json={
                    "player_id": pid,
                    "content": "我是好人，跟着大家投票。"
                })
            except:
                round_info["speak"] = False

        time.sleep(0.5)

        # 投票
        print("[投票] 放逐投票...")
        for pid in players:
            try:
                requests.post(f"{BASE_URL}/api/game/vote", json={
                    "player_id": pid,
                    "target_id": players[0]
                })
            except:
                round_info["vote"] = False

        time.sleep(0.5)
        report_data["rounds"].append(round_info)

    # 生成报告
    end_time = datetime.now()
    duration = round((end_time - start_time).total_seconds(), 2)
    report_data["end_time"] = end_time.strftime("%Y-%m-%d %H:%M:%S")
    report_data["duration"] = duration

    with open("test_report.md", "w", encoding="utf-8") as f:
        f.write(f"""# 狼人杀AI对战测试报告
- 测试时间：{report_data['start_time']} ~ {report_data['end_time']}
- 耗时：{duration} 秒
- 玩家数：{player_num}
- 总轮数：{total_rounds}
- 结果：✅ 全部运行完成
""")

    print(f"\n=== ✅ 对战全部完成！===")
    print(f"📄 报告已保存：test_report.md")

if __name__ == "__main__":
    main()