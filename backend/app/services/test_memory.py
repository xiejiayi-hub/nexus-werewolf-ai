from backend.app.services.memory_service import memory_db

print("--- 开始测试数据模块 ---")

# 1. 模拟存入 16 条消息（故意超过 15 条来触发摘要）
for i in range(1, 17):
    memory_db.save_message(player_id=1, role="VILLAGER", speech=f"这是第 {i} 句话")

# 2. 打印看看是不是前面的被压缩了，只剩最新的几条
print("\n[当前最近记忆列表]:")
recent = memory_db.get_recent_history()
for r in recent:
    print(r)

# 3. 查看发给 AI 的最终上下文（包含摘要+最新对话）
print("\n[发给AI的完整上下文]:")
print(memory_db.get_full_context_for_ai())

# 4. 测试信任矩阵
memory_db.update_trust_matrix(player_id=1, new_trust_scores={"2": 80, "3": 10})
print("\n[当前信任矩阵]:", memory_db.redis.get("game:trust_matrix"))