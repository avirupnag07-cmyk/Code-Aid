# Go diagnostic fixture

`broken.go` returns no value from a function declared to return `int` on line
3. The adapter uses `go tool compile`, never starts a Go program, and marks the
fixture blocked when a runnable Go toolchain is unavailable.

Expected diagnostic: `broken.go`, line 3, error, tool `go`.
