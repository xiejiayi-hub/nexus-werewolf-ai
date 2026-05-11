# backend/app/core/game_state.py - 修改 resolve_night 和 start_night_phase

from typing import List, Dict, Optional
from enum import Enum
import random

class Role(str, Enum):
    WEREWOLF = "WEREWOLF"
    SEER = "SEER"
    VILLAGER = "VILLAGER"
    WITCH = "WITCH"
    HUNTER = "HUNTER"

class GamePhase(str, Enum):
    WAITING = "WAITING"
    NIGHT_WOLF = "NIGHT_WOLF"
    NIGHT_SEER = "NIGHT_SEER"
    NIGHT_WITCH = "NIGHT_WITCH"
    DAY_DISCUSSION = "DAY_DISCUSSION"
    DAY_VOTE = "DAY_VOTE"
    GAME_OVER = "GAME_OVER"

class GameStateMachine:
    def __init__(self):
        self.players: List[Dict] = []
        self.phase: GamePhase = GamePhase.WAITING
        self.alive_players: List[int] = []
        self.current_speaker: Optional[int] = None
        self.speak_order: List[int] = []
        self.votes: Dict[int, int] = {}
        self.round: int = 0
        
        self.wolf_votes: Dict[int, int] = {}
        self.seer_target: Optional[int] = None
        self.witch_save: Optional[int] = None
        self.witch_poison: Optional[int] = None
        self.killed_target: Optional[int] = None
        
    def assign_roles(self, player_ids: List[int]) -> Dict[int, Role]:
        roles = [Role.WEREWOLF, Role.WEREWOLF, Role.SEER,
                 Role.VILLAGER, Role.VILLAGER, Role.VILLAGER]
        random.shuffle(roles)

        role_assignment = {}
        for i, player_id in enumerate(player_ids):
            role_assignment[player_id] = roles[i]

        self.players = [{"id": pid, "role": role_assignment[pid], "alive": True}
                        for pid in player_ids]
        self.alive_players = player_ids.copy()
        return role_assignment

    def start_night_phase(self):
        """开始夜晚阶段"""
        self.phase = GamePhase.NIGHT_WOLF
        self.wolf_votes = {}
        self.seer_target = None
        self.witch_save = None
        self.witch_poison = None
        self.killed_target = None
        print(f"[夜晚] 进入夜晚阶段，存活玩家: {self.alive_players}")
        return self.phase

    def record_wolf_vote(self, wolf_id: int, target_id: int):
        if self.phase == GamePhase.NIGHT_WOLF:
            self.wolf_votes[wolf_id] = target_id

    def resolve_wolf_kill(self) -> Optional[int]:
        if not self.wolf_votes:
            return None
        
        vote_count = {}
        for target in self.wolf_votes.values():
            if target in self.alive_players:
                vote_count[target] = vote_count.get(target, 0) + 1
        
        if not vote_count:
            return None
        
        max_votes = max(vote_count.values())
        candidates = [pid for pid, count in vote_count.items() if count == max_votes]
        
        if len(candidates) == 1:
            self.killed_target = candidates[0]
            return self.killed_target
        return None

    def record_seer_check(self, target_id: int):
        if self.phase == GamePhase.NIGHT_SEER:
            self.seer_target = target_id
            print(f"[预言家] 记录查验目标: {target_id}")

    def get_seer_result(self) -> Optional[Role]:
        """获取预言家查验结果 - 返回Role而不是字符串"""
        if self.seer_target is None:
            return None
        for player in self.players:
            if player["id"] == self.seer_target:
                # 确保返回正确的角色
                return player["role"]
        return None

    def record_witch_action(self, save_target: Optional[int] = None, poison_target: Optional[int] = None):
        """记录女巫行动"""
        if self.phase == GamePhase.NIGHT_WITCH:
            if save_target is not None:
                self.witch_save = save_target
            if poison_target is not None:
                self.witch_poison = poison_target
            print(f"[女巫行动] 救: {save_target}, 毒: {poison_target}")

    def resolve_night(self):
        """解决夜晚阶段 - 返回被杀和毒死的玩家"""
        # 1. 狼人杀人
        killed = self.resolve_wolf_kill()
        
        # 2. 女巫救人/毒人
        final_killed = killed
        poisoned = None
        
        # 如果女巫救了被杀的人
        if self.witch_save and killed == self.witch_save:
            final_killed = None
            print(f"[夜晚] 女巫救下了 {self.witch_save}")
        
        # 女巫毒人
        if self.witch_poison:
            poisoned = self.witch_poison
            print(f"[夜晚] 女巫毒死了 {self.witch_poison}")
        
        # 3. 执行死亡
        deaths = []
        if final_killed:
            self.eliminate(final_killed, silent=True)
            deaths.append(final_killed)
        if poisoned:
            self.eliminate(poisoned, silent=True)
            deaths.append(poisoned)
        
        # 清空夜晚数据
        self.witch_save = None
        self.witch_poison = None
        self.killed_target = None
        
        print(f"[夜晚] 死亡玩家: {deaths if deaths else '无人死亡'}")
        return deaths

    def start_day_phase(self):
        """开始白天阶段"""
        self.phase = GamePhase.DAY_DISCUSSION
        
        # 按数字顺序排序（顺时针）
        self.speak_order = sorted([p for p in self.alive_players if p in self.alive_players])
        
        print(f"[DEBUG] 发言顺序(顺时针): {self.speak_order}")
        
        # 取出第一个发言者
        if self.speak_order:
            self.current_speaker = self.speak_order.pop(0)
            print(f"[DEBUG] 第一个发言者: {self.current_speaker}")
            print(f"[DEBUG] 剩余发言者: {self.speak_order}")
        else:
            self.current_speaker = None
            print(f"[DEBUG] 没有存活玩家")
        
        self.round += 1

    def next_speaker(self) -> Optional[int]:
        """返回下一个发言者，如果没有则返回None"""
        if not self.speak_order:
            print("发言队列为空，发言结束")
            return None
        
        self.current_speaker = self.speak_order.pop(0)
        print(f"下一个发言者是: {self.current_speaker}")
        
        return self.current_speaker

    def record_vote(self, voter_id: int, target_id: int):
        """记录投票并更新信任度"""
        self.votes[voter_id] = target_id
        
        # 投票一致性检测：如果AI投票给最终被淘汰的狼人，增强信任
        # 这个可以在淘汰结果出来后做贝叶斯更新
        from app.services.memory_service import memory_db
        if memory_db:
            # 记录投票行为，用于后续信任更新
            memory_db.save_vote(self.round, voter_id, target_id)

    def calculate_elimination(self) -> Optional[int]:
        if not self.votes:
            return None

        vote_count = {}
        for target in self.votes.values():
            vote_count[target] = vote_count.get(target, 0) + 1

        max_votes = max(vote_count.values())
        candidates = [pid for pid, count in vote_count.items() if count == max_votes]

        if len(candidates) == 1:
            return candidates[0]
        return None

    def eliminate(self, player_id: int, silent: bool = False):
        for player in self.players:
            if player["id"] == player_id:
                player["alive"] = False
                break
        if player_id in self.alive_players:
            self.alive_players.remove(player_id)
        
        if not silent:
            self.votes = {}
        
        # 检查游戏是否结束
        if self.check_game_over():
            self.phase = GamePhase.GAME_OVER

    def check_game_over(self) -> bool:
        werewolves_alive = [p for p in self.players
                           if p["role"] == Role.WEREWOLF and p["alive"]]
        villagers_alive = [p for p in self.players
                          if p["role"] != Role.WEREWOLF and p["alive"]]

        if len(werewolves_alive) == 0:
            return True
        if len(werewolves_alive) >= len(villagers_alive):
            return True
        return False

    def get_winner(self) -> Optional[str]:
        werewolves_alive = [p for p in self.players
                           if p["role"] == Role.WEREWOLF and p["alive"]]
        if len(werewolves_alive) == 0:
            return "好人胜利！"
        villagers_alive = [p for p in self.players
                          if p["role"] != Role.WEREWOLF and p["alive"]]
        if len(werewolves_alive) >= len(villagers_alive):
            return "狼人胜利！"
        return None