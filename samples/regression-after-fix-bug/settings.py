"""Configuration helper showing a regression after a lookup change."""


def load_timeout(config: dict) -> int:
    # A prior fix made explicitly configured values work but removed the default.
    return config["timeout"]
