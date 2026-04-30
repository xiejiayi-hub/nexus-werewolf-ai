from memory_service import memory_db

print("--- 开始测试数据模块 ---")

# 1. 模拟存入 16 条消息（触发摘要逻辑）
for i in range(1, 17):
    # 这里我们模拟 AI 返回了信任评分
    # 假设 AI 在第 16 句话时，评价了 2 号和 3 号
    test_scores = {"2": 80, "3": 10} if i == 16 else None
    
    memory_db.save_message(
        player_id=1, 
        role="VILLAGER", 
        speech=f"这是第 {i} 句话", 
        trust_scores=test_scores
    )

# 2. 打印最近记忆（应该被清理了前10条，只剩最近几条）
print("\n[当前最近记忆列表]:")
recent = memory_db.get_recent_history()
for r in recent:
    print(r)

# 3. 查看发给 AI 的完整上下文（包含自动生成的摘要）
print("\n[发给AI的完整上下文]:")
print(memory_db.get_full_context_for_ai())

# 4. 【重点】测试贝叶斯信任矩阵
print("\n[查看动态信任矩阵]:")
# 获取完整矩阵
matrix = memory_db.get_trust_matrix()
print(f"1号玩家对其他人的信任评分: {matrix.get('1')}")

# 5. 模拟第二次评价（验证贝叶斯平滑效果）
print("\n--- 模拟第二次评价（验证贝叶斯平滑效果） ---")
# 再次给 2 号打 80 分，看它是否会从 59 慢慢爬升（50*0.7 + 80*0.3 = 59）
memory_db.bayesian_update_trust(evaluator_id=1, target_id=2, evidence_score=80)
new_matrix = memory_db.get_trust_matrix()
print(f"第二次评价后，1号对2号的信任分: {new_matrix['1']['2']}")