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

    def start_day_phase(self):
        self.phase = GamePhase.DAY_DISCUSSION
        self.speak_order = self.alive_players.copy()
        random.shuffle(self.speak_order)
        self.current_speaker = self.speak_order.pop(0) if self.speak_order else None
        self.round += 1
        return self.current_speaker

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

    def eliminate(self, player_id: int):
        for player in self.players:
            if player["id"] == player_id:
                player["alive"] = False
                break
        if player_id in self.alive_players:
            self.alive_players.remove(player_id)
        self.votes = {}

        if self.check_game_over():
            self.phase = GamePhase.GAME_OVER
        else:
            self.phase = GamePhase.NIGHT_WOLF

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
