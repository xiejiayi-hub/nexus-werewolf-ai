import redis
import json
import time  # 必须加这一行！
from typing import List, Dict

class MemoryService:
    def __init__(self):
        try:
            self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 数据中心已就绪 (Day 5-6 增强版)")
        except Exception as e:
            print(f"❌ Redis 连接失败: {e}")
        
        # 定义 Redis 的键名
        self.HISTORY_KEY = "game:history"
        self.SUMMARY_KEY = "game:summary"
        self.TRUST_KEY = "game:trust_matrix"
        self.VOTE_KEY = "game:votes" 

        # 贝叶斯更新权重
        self.ALPHA = 0.7 
        self.MAX_HISTORY_LEN = 15

    # ================= Day 1 & 4 任务 =================

    def save_message(self, player_id: int, role: str, speech: str, trust_scores: Dict[str, int] = None):
        msg_obj = {"player_id": player_id, "role": role, "speech": speech}
        self.redis.rpush(self.HISTORY_KEY, json.dumps(msg_obj))
        self.check_and_summarize()

        if trust_scores:
            for target_id, evidence_score in trust_scores.items():
                self.bayesian_update_trust(
                    evaluator_id=player_id, 
                    target_id=int(target_id), 
                    evidence_score=int(evidence_score)
                )

    def get_recent_history(self) -> List[Dict]:
        records = self.redis.lrange(self.HISTORY_KEY, 0, -1)
        return [json.loads(record) for record in records]

    # ================= Day 2 任务 =================

    def check_and_summarize(self):
        current_len = self.redis.llen(self.HISTORY_KEY)
        if current_len > self.MAX_HISTORY_LEN:
            old_messages_json = self.redis.lrange(self.HISTORY_KEY, 0, 9)
            old_messages = [json.loads(m) for m in old_messages_json]
            text_to_summarize = " ".join([f"{m['player_id']}号说:{m['speech']}" for m in old_messages])
            new_summary = self._mock_call_llm_summary(text_to_summarize)
            existing_summary = self.redis.get(self.SUMMARY_KEY) or ""
            updated_summary = existing_summary + "\n" + new_summary
            self.redis.set(self.SUMMARY_KEY, updated_summary)
            self.redis.ltrim(self.HISTORY_KEY, 10, -1)
            print("🔄 触发记忆压缩机制！")

    def _mock_call_llm_summary(self, text: str) -> str:
        return f"[AI自动摘要: 前期讨论中，玩家们发表了各自的意见。]"

    def get_full_context_for_ai(self) -> str:
        summary = self.redis.get(self.SUMMARY_KEY) or "暂无早期摘要。"
        recent = self.get_recent_history()
        recent_text = "".join([f"玩家[{m['player_id']}]({m['role']}): {m['speech']}\n" for m in recent])
        return f"【历史摘要】\n{summary}\n\n【近期对话】\n{recent_text}"
    
    # ================= Day 3-6 核心任务：贝叶斯与行为更新 =================

    def update_trust_by_behavior(self, evaluator_id: int, target_id: int, behavior_type: str):
        """根据投票一致性或逻辑矛盾调整信任度"""
        behavior_scores = {"vote_consistent": 85, "contradiction": 15}
        score = behavior_scores.get(behavior_type, 50)
        self.bayesian_update_trust(evaluator_id, target_id, score)

    def bayesian_update_trust(self, evaluator_id: int, target_id: int, evidence_score: int):
        matrix = self.get_trust_matrix()
        eval_key, target_key = str(evaluator_id), str(target_id)
        if eval_key not in matrix:
            matrix[eval_key] = {str(i): 50 for i in range(1, 7)}
        prior_score = matrix[eval_key].get(target_key, 50)
        posterior_score = (prior_score * self.ALPHA) + (evidence_score * (1 - self.ALPHA))
        posterior_score = max(0, min(100, round(posterior_score, 2)))
        matrix[eval_key][target_key] = posterior_score
        self.redis.set(self.TRUST_KEY, json.dumps(matrix))
        print(f"📈 贝叶斯更新：玩家{evaluator_id}对玩家{target_id}的信任度 -> {posterior_score}")

    # ================= 任务 2 & 3：记录与导出 =================

    def save_vote(self, round_num: int, voter_id: int, target_id: int):
        """记录投票用于导出"""
        vote_info = {
            "round": round_num,
            "voter": voter_id,
            "target": target_id,
            "timestamp": time.time()
        }
        self.redis.rpush(self.VOTE_KEY, json.dumps(vote_info))

    def get_trust_matrix(self) -> Dict:
        """获取完整的 N x N 信任矩阵"""
        data = self.redis.get(self.TRUST_KEY)
        if data:
            return json.loads(data)
        return {str(i): {str(j): 50 for j in range(1, 7)} for i in range(1, 7)}

    def export_game_logs(self) -> Dict:
        """导出整场比赛 JSON 存档"""
        history = self.get_recent_history()
        summary = self.redis.get(self.SUMMARY_KEY) or ""
        matrix = self.get_trust_matrix()
        votes_raw = self.redis.lrange(self.VOTE_KEY, 0, -1)
        votes = [json.loads(v) for v in votes_raw]
        
        export_data = {
            "game_id": f"game_{int(time.time())}",
            "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "final_summary": summary,
            "full_history": history,
            "voting_records": votes,
            "final_trust_matrix": matrix
        }
        
        with open("game_archive.json", "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        print("💾 比赛日志已导出至 game_archive.json")
        return export_data

# 实例化
memory_db = MemoryService()