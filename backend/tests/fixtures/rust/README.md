# Rust diagnostic fixture

`broken.rs` has an empty body for a function declared to return `i32` on line
1. The adapter uses Rust metadata/check mode and never runs the source. Cargo
and rustc must both be runnable for this fixture to receive a native check;
otherwise the test records an explicit blocked-tool result.

Expected diagnostic: `broken.rs`, line 1, error, tool `cargo` or `rustc`.
