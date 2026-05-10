from memory_service import memory_db

print("--- 🏁 开始 Nexus-Werewolf AI 最终验收测试 (Day 8) ---")

# 1. 模拟游戏进行
print("\n[1] 模拟对话与信任更新...")
memory_db.save_message(1, "WEREWOLF", "我觉得3号是预言家。", trust_scores={"3": 10})

# 2. 模拟投票
print("[2] 模拟投票...")
memory_db.save_vote(round_num=1, voter_id=1, target_id=3)

# 3. [新功能测试] 模拟淘汰
print("[3] 模拟淘汰记录...")
memory_db.save_elimination(round_num=1, player_id=3, role="SEER", reason="killed_by_wolf")

# 4. 模拟行为更新
print("[4] 模拟行为评分...")
memory_db.update_trust_by_behavior(2, 1, "contradiction")

# 5. [核心测试] 最终导出
print("\n[5] 运行最终全量导出接口...")
final_archive = memory_db.export_game_to_json()

print(f"\n✅ 测试通过！")
print(f"存档详情: {final_archive['export_time']}")
print(f"累计发言: {final_archive['data_metrics']['total_speeches']}")
print(f"出局人数: {final_archive['data_metrics']['total_eliminations']}")
print(f"请检查项目根目录下的 final_game_log_xxx.json 文件。")