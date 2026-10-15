"""Minimal checkout tax helper with a reproducible type bug."""


def add_tax(amount: float, tax_rate: str) -> float:
    tax = "{}%".format(tax_rate)
    return amount + tax
