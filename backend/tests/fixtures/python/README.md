# Python diagnostic fixture

This deterministic fixture contains a syntax defect in `broken.py`: the
expression on line 2 is incomplete. It is parsed with Python's `ast` module;
the fixture is never imported or executed by the API process.

Expected diagnostic: `broken.py`, line 2, error, tool `ast`.
