# IFRL

IFRL is the shared home for the suite's Nix dependency definitions and Bazel
worker/REAPI execution machinery.

## Extraction boundary

- `flake.nix` is the common Nix dependency flake. The current suite-wide
  nixpkgs pin is shared here.
- `nix/clients/<client>/` preserves each client's current Nix layer and lock
  data. These profiles intentionally remain divergent during this extraction.
- `bazel/ixyk/` preserves IXYK's local and clustered NativeLink REAPI worker
  setup.
- `bazel/wruh/` preserves Wruh's Bazel wrapper, dependency extensions, and
  remote artifact action support.
- Client `MODULE.bazel`, lockfiles, BUILD files, and target graphs remain in
  their client repositories. Client Nix closures are inputs to the IFRL worker
  interface; the extraction does not assume a single Bazel configuration.

The profile copies are an extraction draft. They preserve current differences
so the suite can perform a later, focused unification and validation pass.

## Source snapshots

The profile files were copied from these source revisions (client-specific
Bazel modules and target graphs were not copied):

| Profile | Source revision |
| --- | --- |
| IXYK | `2aac3608ff23` |
| WRUH | `48ddcd116b8f` |
| AYXG | `051368767f23` |
| AKVI | `96ae1b531556` |
| TMVM | `1c3d72e59e83` |
| IZOM | `9042b60` |
