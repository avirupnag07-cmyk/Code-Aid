# Settings timeout loader

This regression sample models a common configuration fix: replacing an
optional lookup with direct indexing. Existing deployments that omit the
timeout now fail with `KeyError`, and the metadata supplies that missing-key
case as a generated pytest reproduction.
