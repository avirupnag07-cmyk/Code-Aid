# Profile username normalizer

The upstream profile payload sometimes contains a numeric identifier in the
username field. This project intentionally calls a string method without
validating the value first, producing the supplied `AttributeError`. A correct
boundary normalization should return the string `"42"` for the sample input.
