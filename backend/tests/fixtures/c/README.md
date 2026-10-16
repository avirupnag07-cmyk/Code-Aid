# C diagnostic fixture

`broken.c` has a non-void function with an empty return statement on line 1.
The adapter invokes the compiler's syntax-only mode and does not link or run
the source.

Expected diagnostic: `broken.c`, line 1, error, tool `gcc`.
