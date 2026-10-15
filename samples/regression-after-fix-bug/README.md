# Settings timeout loader

This regression sample models a common configuration fix: replacing an
optional lookup with direct indexing. Existing deployments that omit the
timeout now fail with `KeyError`. The metadata supplies an expected default of
`30` so a proposed fix can be compared against a meaningful pytest case.
