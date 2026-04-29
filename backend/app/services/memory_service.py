import redis
import json
from typing import List, Dict

class MemoryService:
    def __init__(self):
        # 连接本地 Redis
        try:
            self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.redis.ping() # 测试连接
            print("✅ Redis 连接成功！数据服务已启动。")
        except Exception as e:
            print(f"❌ Redis 连接失败，请检查是否启动了 Redis! 错误: {e}")
        
        # 定义 Redis 的键名
        self.HISTORY_KEY = "game:history"      # 存对话列表
        self.SUMMARY_KEY = "game:summary"      # 存历史摘要
        self.TRUST_KEY = "game:trust_matrix"   # 存信任矩阵
        
        # 组长规定的：超过 15 条自动触发摘要
        self.MAX_HISTORY_LEN = 15

    # ================= Day 1 任务 =================

    def save_message(self, player_id: int, role: str, speech: str):
        """保存单条发言记录到 Redis"""
        msg_obj = {
            "player_id": player_id,
            "role": role,
            "speech": speech
        }
        # 将字典转为 JSON 字符串，从右侧推入列表
        self.redis.rpush(self.HISTORY_KEY, json.dumps(msg_obj))
        
        # 触发 Day 2 的任务：检查是否需要做摘要
        self.check_and_summarize()

    def get_recent_history(self) -> List[Dict]:
        """获取最近的历史记录"""
        # 取出所有列表中的记录
        records = self.redis.lrange(self.HISTORY_KEY, 0, -1)
        return [json.loads(record) for record in records]

    # ================= Day 2 任务 =================

    def check_and_summarize(self):
        """实现对话摘要功能 (超过15条自动生成摘要)"""
        current_len = self.redis.llen(self.HISTORY_KEY)
        
        if current_len > self.MAX_HISTORY_LEN:
            # 取出最老的 10 条消息用来做摘要
            old_messages_json = self.redis.lrange(self.HISTORY_KEY, 0, 9)
            old_messages = [json.loads(m) for m in old_messages_json]
            
            # 把这些消息拼成一段文本
            text_to_summarize = " ".join([f"{m['player_id']}号说:{m['speech']}" for m in old_messages])
            
            # TODO: 这里应该调用【算法同学A】写的大模型接口。
            # 为了不阻塞你的进度，这里我们先自己写个伪摘要，等 A 写好了替换掉这个函数即可。
            new_summary = self._mock_call_llm_summary(text_to_summarize)
            
            # 把新摘要追加到 Redis 中
            existing_summary = self.redis.get(self.SUMMARY_KEY) or ""
            updated_summary = existing_summary + "\n" + new_summary
            self.redis.set(self.SUMMARY_KEY, updated_summary)
            
            # 摘要做完了，把最老的 10 条从列表中删除，保留最新的
            self.redis.ltrim(self.HISTORY_KEY, 10, -1)
            print("🔄 触发记忆压缩机制！已生成摘要并清理旧记忆。")

    def _mock_call_llm_summary(self, text: str) -> str:
        """这是一个假的大模型调用，等算法同学写好 llm_service 后换掉它"""
        return f"[AI自动摘要: 前期讨论中，玩家们发表了各自的意见。]"

    def update_trust_matrix(self, player_id: int, new_trust_scores: Dict[str, int]):
        """
        更新信任矩阵
        组长协议: "trust_scores": {"1": 100, "2": 50, ...}
        """
        # 获取现有的整体矩阵，如果没有就建个空的
        matrix_str = self.redis.get(self.TRUST_KEY)
        if matrix_str:
            matrix = json.loads(matrix_str)
        else:
            matrix = {}

        # 更新这个玩家对其他人的信任分数
        matrix[str(player_id)] = new_trust_scores
        
        # 存回 Redis
        self.redis.set(self.TRUST_KEY, json.dumps(matrix))

    def get_full_context_for_ai(self) -> str:
        """
        【核心接口】注入对话历史到 AI 请求中
        组长要求：确保能注入对话历史到 AI 请求中
        """
        summary = self.redis.get(self.SUMMARY_KEY) or "暂无早期摘要。"
        recent = self.get_recent_history()
        
        recent_text = ""
        for m in recent:
            recent_text += f"玩家[{m['player_id']}]({m['role']}): {m['speech']}\n"
            
        full_context = f"【历史摘要】\n{summary}\n\n【近期对话】\n{recent_text}"
        return full_context

# 实例化一个全局对象，供 FastAPI 后端直接导入调用
memory_db = MemoryService()