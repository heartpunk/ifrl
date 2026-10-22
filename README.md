# IFRL

IFRL is the shared home for the suite's Nix dependency definitions and Bazel
worker/REAPI execution machinery.

## Extraction boundary

- `flake.nix` is the common Nix dependency flake. The current suite-wide
  nixpkgs pin is shared here.
- `MODULE.bazel` publishes the shared worker extensions and rules to Bazel
  clients as an explicit, pinned dependency.
- `nix/clients/<client>/` preserves each client's current Nix layer and lock
  data. These profiles intentionally remain divergent during this extraction.
- `bazel/ixyk/` preserves IXYK's local and clustered NativeLink REAPI worker
  setup.
- `bazel/wruh/` preserves Wruh's Bazel wrapper, dependency extensions, and
  remote artifact action support.
- IXYK and Wruh load their shared Python/native dependency extensions and
  Wruh's artifact action rule from this Bazel module; client module graphs and
  target graphs remain local.
- Client `MODULE.bazel`, lockfiles, BUILD files, and target graphs remain in
  their client repositories. Client Nix closures are inputs to the IFRL worker
  interface; the extraction does not assume a single Bazel configuration.

The profile copies are an extraction draft. They preserve current differences
so the suite can perform a later, focused unification and validation pass.

## Suite source-reference audit

`ci/suite_refs.py` accepts explicit checkout roots, finds Nix, Bazel, Lake,
Lean toolchain, and workflow files below them, extracts source references, and
compares the resolved revisions and declared selectors. Run it in the IFRL
development shell so Nix, Bazel, and Lean syntax use the flake-provided
ast-grep and experimental Lean grammar:

```sh
nix develop --command python3 ci/suite_refs.py \
  --repo ifrl=/path/to/ifrl \
  --repo ayxg=/path/to/ayxg \
  --repo ixyk=/path/to/ixyk \
  --repo wruh=/path/to/wruh \
  --repo utem=/path/to/utem \
  --repo ufda=/path/to/ufda
```

The roots are explicit; the audit discovers build files within each selected
checkout and does not search the machine for repositories. Its discovery,
extraction, and comparison phases are separate. The in-memory records use
Dublin Core terms for document metadata and PROV-O terms for entity derivation
and activity inputs/outputs. Findings distinguish mismatches from sources that
the current static extraction cannot resolve.

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
