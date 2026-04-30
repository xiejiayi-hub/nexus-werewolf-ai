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

        # 贝叶斯更新权重 (Alpha值)
        self.ALPHA = 0.7 
        
        # 组长规定的：超过 15 条自动触发摘要
        self.MAX_HISTORY_LEN = 15

    # ================= Day 1 & 4 增强版任务 =================

    def save_message(self, player_id: int, role: str, speech: str, trust_scores: Dict[str, int] = None):
        """
        保存单条发言记录到 Redis，并同步更新信任矩阵
        """
        msg_obj = {
            "player_id": player_id,
            "role": role,
            "speech": speech
        }
        # 使用类定义的 HISTORY_KEY
        self.redis.rpush(self.HISTORY_KEY, json.dumps(msg_obj))
        
        # 触发摘要检查
        self.check_and_summarize()

        # 【Day 4 核心】如果传了新的评分，触发贝叶斯更新
        if trust_scores:
            for target_id, evidence_score in trust_scores.items():
                self.bayesian_update_trust(
                    evaluator_id=player_id, 
                    target_id=int(target_id), 
                    evidence_score=int(evidence_score)
                )

    def get_recent_history(self) -> List[Dict]:
        """获取最近的历史记录"""
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
            
            # TODO: 等 A 组写好了替换掉这个函数
            new_summary = self._mock_call_llm_summary(text_to_summarize)
            
            # 把新摘要追加到 Redis 中
            existing_summary = self.redis.get(self.SUMMARY_KEY) or ""
            updated_summary = existing_summary + "\n" + new_summary
            self.redis.set(self.SUMMARY_KEY, updated_summary)
            
            # 摘要做完了，保留最新的
            self.redis.ltrim(self.HISTORY_KEY, 10, -1)
            print("🔄 触发记忆压缩机制！已生成摘要并清理旧记忆。")

    def _mock_call_llm_summary(self, text: str) -> str:
        """假摘要生成"""
        return f"[AI自动摘要: 前期讨论中，玩家们发表了各自的意见。]"

    def get_full_context_for_ai(self) -> str:
        """注入对话历史到 AI 请求中"""
        summary = self.redis.get(self.SUMMARY_KEY) or "暂无早期摘要。"
        recent = self.get_recent_history()
        
        recent_text = ""
        for m in recent:
            recent_text += f"玩家[{m['player_id']}]({m['role']}): {m['speech']}\n"
            
        full_context = f"【历史摘要】\n{summary}\n\n【近期对话】\n{recent_text}"
        return full_context
    
    # ================= Day 3-4 核心任务：贝叶斯信任更新 =================

    def bayesian_update_trust(self, evaluator_id: int, target_id: int, evidence_score: int):
        """使用贝叶斯平滑公式更新信任度"""
        matrix = self.get_trust_matrix()
        
        eval_key = str(evaluator_id)
        target_key = str(target_id)
        
        # 初始化评价行
        if eval_key not in matrix:
            matrix[eval_key] = {str(i): 50 for i in range(1, 7)}
        
        # 获取先验分数
        prior_score = matrix[eval_key].get(target_key, 50)
        
        # 贝叶斯计算: 后验 = 先验 * Alpha + 证据 * (1 - Alpha)
        posterior_score = (prior_score * self.ALPHA) + (evidence_score * (1 - self.ALPHA))
        posterior_score = max(0, min(100, round(posterior_score, 2)))
        
        # 更新并保存
        matrix[eval_key][target_key] = posterior_score
        self.redis.set(self.TRUST_KEY, json.dumps(matrix))
        print(f"📈 贝叶斯更新：玩家{evaluator_id}对玩家{target_id}的信任度更新为 {posterior_score}")

    def get_trust_matrix(self) -> Dict:
        """获取完整的 N x N 信任矩阵"""
        data = self.redis.get(self.TRUST_KEY)
        if data:
            return json.loads(data)
        # 初始化 6x6 矩阵
        return {str(i): {str(j): 50 for j in range(1, 7)} for i in range(1, 7)}

# 实例化
memory_db = MemoryService()