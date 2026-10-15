"""Profile normalization example with an unexpected runtime type."""


def normalize_username(value: str) -> str:
    return value.strip().lower()
