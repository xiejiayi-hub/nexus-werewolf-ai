import redis
import json
import time
from typing import List, Dict

class MemoryService:
    def __init__(self):
        self.redis_available = False
        self._memory_trust = {}  # 内存备份
        try:
            self.redis = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.redis.ping()
            print("✅ Redis 数据中心已就绪 (Day 7-8 Final)")
            self.redis_available = True
        except Exception as e:
            print(f"❌ Redis 连接失败: {e}")
            print("将使用内存模式运行")
            self.redis_available = False        
        self.HISTORY_KEY = "game:history"
        self.SUMMARY_KEY = "game:summary"
        self.TRUST_KEY = "game:trust_matrix"
        self.VOTE_KEY = "game:votes" 
        self.ELIMINATION_KEY = "game:eliminations"  # 新增：记录淘汰/死亡信息

        self.ALPHA = 0.7 
        self.MAX_HISTORY_LEN = 15
        
        # 初始化信任矩阵
        self._init_trust_matrix()

    def _init_trust_matrix(self):
        """初始化信任矩阵（所有值50）"""
        default_matrix = {str(i): {str(j): 50 for j in range(1, 7)} for i in range(1, 7)}
        
        if self.redis_available:
            existing = self.redis.get(self.TRUST_KEY)
            if not existing:
                self.redis.set(self.TRUST_KEY, json.dumps(default_matrix))
                print("📊 初始化信任矩阵到 Redis")
        else:
            self._memory_trust = default_matrix

    def save_elimination(self, round_num: int, player_id: int, role: str, reason: str):
        """记录谁出局了"""
        elim_info = {
            "round": round_num,
            "player_id": player_id,
            "role": role,
            "reason": reason,
            "timestamp": time.strftime("%H:%M:%S")
        }
        if self.redis_available:
            self.redis.rpush(self.ELIMINATION_KEY, json.dumps(elim_info))
        else:
            if not hasattr(self, '_memory_eliminations'):
                self._memory_eliminations = []
            self._memory_eliminations.append(elim_info)
        print(f"💀 记录淘汰：玩家{player_id}({role}) 在第{round_num}轮出局，原因：{reason}")

    def export_game_to_json(self) -> Dict:
        """一键导出整场比赛所有维度的 JSON 存档"""
        history = self.get_recent_history()
        
        if self.redis_available:
            summary = self.redis.get(self.SUMMARY_KEY) or ""
            votes_raw = self.redis.lrange(self.VOTE_KEY, 0, -1)
            votes = [json.loads(v) for v in votes_raw]
            elims_raw = self.redis.lrange(self.ELIMINATION_KEY, 0, -1)
            elims = [json.loads(e) for e in elims_raw]
        else:
            summary = getattr(self, '_memory_summary', "")
            votes = getattr(self, '_memory_votes', [])
            elims = getattr(self, '_memory_eliminations', [])
        
        matrix = self.get_trust_matrix()
        
        export_data = {
            "game_id": f"game_{int(time.time())}",
            "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "data_metrics": {
                "total_speeches": len(history),
                "total_votes": len(votes),
                "total_eliminations": len(elims)
            },
            "game_logs": {
                "summary": summary,
                "history": history,
                "votes": votes,
                "eliminations": elims,
                "trust_matrix": matrix
            }
        }
        
        file_name = f"final_game_log_{int(time.time())}.json"
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
            
        print(f"💾 最终存档已导出至：{file_name}")
        return export_data

    def save_message(self, player_id: int, role: str, speech: str, trust_scores: Dict[str, int] = None):
        msg_obj = {"player_id": player_id, "role": role, "speech": speech}
        
        if self.redis_available:
            self.redis.rpush(self.HISTORY_KEY, json.dumps(msg_obj))
        else:
            if not hasattr(self, '_memory_history'):
                self._memory_history = []
            self._memory_history.append(msg_obj)
        
        self.check_and_summarize()
        if trust_scores:
            for target_id, evidence_score in trust_scores.items():
                self.bayesian_update_trust(player_id, int(target_id), int(evidence_score))

    def get_recent_history(self) -> List[Dict]:
        if self.redis_available:
            records = self.redis.lrange(self.HISTORY_KEY, 0, -1)
            return [json.loads(record) for record in records]
        else:
            return getattr(self, '_memory_history', [])

    def check_and_summarize(self):
        current_len = self.redis.llen(self.HISTORY_KEY) if self.redis_available else len(getattr(self, '_memory_history', []))
        
        if current_len > self.MAX_HISTORY_LEN:
            if self.redis_available:
                old_messages_json = self.redis.lrange(self.HISTORY_KEY, 0, 9)
                old_messages = [json.loads(m) for m in old_messages_json]
            else:
                old_messages = getattr(self, '_memory_history', [])[:10]
            
            text_to_summarize = " ".join([f"{m['player_id']}号说:{m['speech']}" for m in old_messages])
            new_summary = self._mock_call_llm_summary(text_to_summarize)
            
            if self.redis_available:
                existing_summary = self.redis.get(self.SUMMARY_KEY) or ""
                updated_summary = existing_summary + "\n" + new_summary
                self.redis.set(self.SUMMARY_KEY, updated_summary)
                self.redis.ltrim(self.HISTORY_KEY, 10, -1)
            else:
                if not hasattr(self, '_memory_summary'):
                    self._memory_summary = ""
                self._memory_summary = self._memory_summary + "\n" + new_summary
                self._memory_history = self._memory_history[10:]
            
            print("🔄 触发记忆压缩机制！")

    def _mock_call_llm_summary(self, text: str) -> str:
        return f"[AI自动摘要: 前期讨论中，玩家们发表了各自的意见。]"

    def get_full_context_for_ai(self) -> str:
        if self.redis_available:
            summary = self.redis.get(self.SUMMARY_KEY) or "暂无早期摘要。"
        else:
            summary = getattr(self, '_memory_summary', "暂无早期摘要。")
        
        recent = self.get_recent_history()
        recent_text = "".join([f"玩家[{m['player_id']}]({m['role']}): {m['speech']}\n" for m in recent])
        return f"【历史摘要】\n{summary}\n\n【近期对话】\n{recent_text}"

    def update_trust_by_behavior(self, evaluator_id: int, target_id: int, behavior_type: str):
        behavior_scores = {"vote_consistent": 85, "contradiction": 15}
        score = behavior_scores.get(behavior_type, 50)
        self.bayesian_update_trust(evaluator_id, target_id, score)

    def bayesian_update_trust(self, evaluator_id: int, target_id: int, evidence_score: int):
        """贝叶斯更新信任度"""
        matrix = self.get_trust_matrix()
        
        eval_key = str(evaluator_id)
        target_key = str(target_id)
        
        if eval_key not in matrix:
            matrix[eval_key] = {str(j): 50 for j in range(1, 7)}
        
        prior_score = matrix[eval_key].get(target_key, 50)
        
        # 贝叶斯更新
        posterior_score = (prior_score * self.ALPHA) + (evidence_score * (1 - self.ALPHA))
        posterior_score = max(0, min(100, round(posterior_score, 2)))
        
        matrix[eval_key][target_key] = posterior_score
        
        if self.redis_available:
            self.redis.set(self.TRUST_KEY, json.dumps(matrix))
            print(f"💾 信任矩阵已保存到 Redis")
        else:
            self._memory_trust = matrix
        
        print(f"📈 贝叶斯更新：玩家{evaluator_id}对玩家{target_id}的信任度 {prior_score} -> {posterior_score}")
        return posterior_score

    def save_vote(self, round_num: int, voter_id: int, target_id: int):
        """记录投票用于导出"""
        vote_info = {
            "round": round_num,
            "voter": voter_id,
            "target": target_id,
            "timestamp": time.time()
        }
        if self.redis_available:
            self.redis.rpush(self.VOTE_KEY, json.dumps(vote_info))
        else:
            if not hasattr(self, '_memory_votes'):
                self._memory_votes = []
            self._memory_votes.append(vote_info)

    def get_trust_matrix(self) -> Dict:
        """获取完整的 N x N 信任矩阵"""
        matrix = None
        
        if self.redis_available:
            data = self.redis.get(self.TRUST_KEY)
            if data:
                try:
                    matrix = json.loads(data)
                except json.JSONDecodeError:
                    matrix = None
        
        if matrix is None:
            if hasattr(self, '_memory_trust') and self._memory_trust:
                matrix = self._memory_trust
            else:
                matrix = {str(i): {str(j): 50 for j in range(1, 7)} for i in range(1, 7)}
        
        # 确保格式正确
        for i in range(1, 7):
            str_i = str(i)
            if str_i not in matrix:
                matrix[str_i] = {}
            for j in range(1, 7):
                str_j = str(j)
                if str_j not in matrix[str_i]:
                    matrix[str_i][str_j] = 50
        
        return matrix


# 实例化
memory_db = MemoryService()