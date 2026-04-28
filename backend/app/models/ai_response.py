from pydantic import BaseModel, Field
from typing import Dict
from enum import Enum

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

class AIResponse(BaseModel):
    player_id: int = Field(..., description="玩家ID，1-6")
    role: Role = Field(..., description="当前身份")
    thought: str = Field(..., description="内心独白")
    speech: str = Field(..., description="公开发言")
    vote_target: int = Field(..., ge=1, le=6)
    trust_scores: Dict[str, int] = Field(..., description="信任值 0-100")
