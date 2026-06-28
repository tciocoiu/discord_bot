import random
import re
from dataclasses import dataclass

from bot.config import Config
from bot.services.names import normalize_name

MENTION_PATTERN = re.compile(r"<@!?(\d+)>")
LOOT_QUANTITY_PATTERN = re.compile(r"^(\d+)\s+(.+)$")


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


def parse_splittable_loot(item: str) -> tuple[int, str] | None:
    """Return (quantity, label) when item is like '400 bes'; None for single items."""
    match = LOOT_QUANTITY_PATTERN.match(item.strip())
    if not match:
        return None
    quantity = int(match.group(1))
    label = match.group(2).strip()
    if quantity <= 1 or not label:
        return None
    return quantity, label


def format_quantity_loot(amount: int, label: str) -> str:
    return f"{amount} {label}"


def split_quantity_loot(
    quantity: int,
    label: str,
    participants: list[Participant],
    config: Config,
) -> list[LootResult]:
    n = len(participants)
    amounts = [quantity // n] * n
    remainder = quantity % n

    if remainder:
        indices = list(range(n))
        weights = [compute_weight(participants[i], config) for i in indices]
        for _ in range(remainder):
            chosen = random.choices(indices, weights=weights, k=1)[0]
            amounts[chosen] += 1
            pick = indices.index(chosen)
            indices.pop(pick)
            weights.pop(pick)

    results: list[LootResult] = []
    for participant, amount in zip(participants, amounts):
        if amount <= 0:
            continue
        results.append(
            LootResult(
                person_key=participant.person_key,
                display_name=participant.display_name,
                discord_user_id=participant.discord_user_id,
                loot_item=format_quantity_loot(amount, label),
            )
        )
    return results


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
        parsed = parse_splittable_loot(item)
        if parsed is not None:
            quantity, label = parsed
            results.extend(split_quantity_loot(quantity, label, participants, config))
            continue

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
