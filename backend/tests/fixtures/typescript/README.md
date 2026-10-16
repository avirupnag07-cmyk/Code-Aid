# TypeScript diagnostic fixture

`broken.ts` has an incomplete initializer on line 1. When the local `tsc`
compiler is present, the adapter runs `tsc --noEmit --pretty false`; otherwise
the diagnostic test records an explicit blocked-tool result.

Expected diagnostic: `broken.ts`, line 1, error, tool `tsc`.
