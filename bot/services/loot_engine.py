import random
import re
from dataclasses import dataclass

from bot.config import Config
from bot.services.names import normalize_name

MENTION_PATTERN = re.compile(r"<@!?(\d+)>")


@dataclass(frozen=True)
class Participant:
    person_key: str
    display_name: str
    discord_user_id: int | None
    miss_streak: int = 0
    activity_points: int = 0


@dataclass(frozen=True)
class LootResult:
    person_key: str
    display_name: str
    discord_user_id: int | None
    loot_item: str


def parse_lines(text: str) -> list[str]:
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


def parse_participant(raw: str) -> tuple[str, str, int | None]:
    """Return (person_key, display_name, discord_user_id)."""
    mention = MENTION_PATTERN.fullmatch(raw.strip())
    if mention:
        user_id = int(mention.group(1))
        return str(user_id), f"<@{user_id}>", user_id
    normalized = normalize_name(raw)
    return normalized, normalized, None


def compute_weight(participant: Participant, config: Config) -> float:
    return (
        config.base_weight
        + participant.miss_streak * config.bad_luck_weight
        + participant.activity_points * config.activity_weight
    )


def distribute_loot(
    participants: list[Participant],
    loot_items: list[str],
    config: Config,
) -> list[LootResult]:
    if not participants:
        raise ValueError("People list cannot be empty")
    if not loot_items:
        raise ValueError("Loot list cannot be empty")

    results: list[LootResult] = []
    for item in loot_items:
        weights = [compute_weight(p, config) for p in participants]
        winner = random.choices(participants, weights=weights, k=1)[0]
        results.append(
            LootResult(
                person_key=winner.person_key,
                display_name=winner.display_name,
                discord_user_id=winner.discord_user_id,
                loot_item=item,
            )
        )
    return results
