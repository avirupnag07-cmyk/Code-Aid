# JavaScript diagnostic fixture

`broken.js` has a missing initializer expression on line 1. The adapter uses
Node's `--check` mode, which parses the source without running it.

Expected diagnostic: `broken.js`, line 1, error, tool `node`.
