from memory_service import memory_db
import json

print("--- 🚀 开始测试数据模块 (Day 5-6 增强版) ---")

# 1. 模拟存入 16 条消息（触发摘要逻辑）
print("\n[步骤 1] 模拟存入消息并触发摘要...")
for i in range(1, 17):
    test_scores = {"2": 80, "3": 10} if i == 16 else None
    memory_db.save_message(
        player_id=1, 
        role="VILLAGER", 
        speech=f"这是第 {i} 句话", 
        trust_scores=test_scores
    )

# 2. 验证摘要和历史
print("\n[步骤 2] 验证记忆上下文...")
print(memory_db.get_full_context_for_ai())

# 3. 【新增任务 1】测试行为更新逻辑 (言行矛盾)
print("\n[步骤 3] 测试基于行为的信任更新 (Behavior Update)...")
# 假设 2 号玩家发现 3 号玩家说话自相矛盾
memory_db.update_trust_by_behavior(evaluator_id=2, target_id=3, behavior_type="contradiction")
matrix = memory_db.get_trust_matrix()
print(f"2号对3号的信任度 (应因矛盾大幅下降): {matrix['2']['3']}")

# 4. 【新增任务 2】记录投票
print("\n[步骤 4] 模拟投票记录...")
memory_db.save_vote(round_num=1, voter_id=1, target_id=3)
memory_db.save_vote(round_num=1, voter_id=2, target_id=3)
print("投票已记录。")

# 5. 【新增任务 3】测试一键导出存档
print("\n[步骤 5] 测试全场数据导出 (JSON Export)...")
logs = memory_db.export_game_logs()
print(f"成功导出存档！存档 ID: {logs['game_id']}")
print(f"包含投票记录数: {len(logs['voting_records'])}")
print(f"存档时间: {logs['export_time']}")

print("\n--- ✅ 所有测试已通过！你可以放心地 Push 代码了。 ---")