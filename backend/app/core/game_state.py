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
        
        # 夜晚阶段数据
        self.wolf_votes: Dict[int, int] = {}  # 狼人投票 {狼人ID: 目标ID}
        self.seer_target: Optional[int] = None  # 预言家查验目标
        self.witch_save: Optional[int] = None  # 女巫救的人
        self.witch_poison: Optional[int] = None  # 女巫毒的人
        self.killed_target: Optional[int] = None  # 夜晚被杀的人
        
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
        \"\"\"进入夜晚阶段\"\"\"
        self.phase = GamePhase.NIGHT_WOLF
        self.wolf_votes = {}
        self.seer_target = None
        self.witch_save = None
        self.witch_poison = None
        self.killed_target = None
        return self.phase

    def record_wolf_vote(self, wolf_id: int, target_id: int):
        \"\"\"狼人投票杀人\"\"\"
        if self.phase == GamePhase.NIGHT_WOLF:
            self.wolf_votes[wolf_id] = target_id

    def resolve_wolf_kill(self) -> Optional[int]:
        \"\"\"结算狼人杀人结果\"\"\"
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
        return None  # 平票，无人死亡

    def record_seer_check(self, target_id: int):
        \"\"\"预言家查验\"\"\"
        if self.phase == GamePhase.NIGHT_SEER:
            self.seer_target = target_id

    def get_seer_result(self) -> Optional[str]:
        \"\"\"获取查验结果\"\"\"
        if self.seer_target is None:
            return None
        for player in self.players:
            if player["id"] == self.seer_target and player["alive"]:
                return player["role"]
        return None

    def resolve_night(self):
        \"\"\"结算整个夜晚\"\"\"
        # 1. 先结算狼人杀人
        killed = self.resolve_wolf_kill()
        
        if killed:
            # 女巫救人（简化版，暂不实现女巫逻辑）
            pass
        
        # 2. 执行死亡
        if self.killed_target:
            self.eliminate(self.killed_target, silent=True)
        
        # 3. 进入白天
        self.start_day_phase()
        return self.killed_target

    def start_day_phase(self):
        self.phase = GamePhase.DAY_DISCUSSION
        self.speak_order = self.alive_players.copy()
        random.shuffle(self.speak_order)
        self.current_speaker = self.speak_order.pop(0) if self.speak_order else None
        self.round += 1

    def next_speaker(self) -> Optional[int]:
        if not self.speak_order:
            self.phase = GamePhase.DAY_VOTE
            return None
        self.current_speaker = self.speak_order.pop(0)
        return self.current_speaker

    def record_vote(self, voter_id: int, target_id: int):
        if voter_id in self.alive_players and target_id in self.alive_players:
            self.votes[voter_id] = target_id

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
        
        if self.check_game_over():
            self.phase = GamePhase.GAME_OVER
        elif not silent:
            self.start_night_phase()

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
