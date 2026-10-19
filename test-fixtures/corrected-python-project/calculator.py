def total_with_tax(amount, tax_rate):
    """Return the total after applying a percentage tax rate."""
    return amount * (1 + float(tax_rate) / 100)
