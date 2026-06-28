def normalize_name(name: str) -> str:
    """Normalize a display/boss name for storage and lookup."""
    return name.strip().lower()
