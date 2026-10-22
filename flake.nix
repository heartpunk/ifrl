{
  description = "Shared suite Nix dependencies and Bazel worker infrastructure";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/e79d204daf01f8a877f7b2ce7324874ce9c84676";
    lean4-nix = {
      url = "github:heartpunk/lean4-nix/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    rust-overlay = {
      url = "github:oxalica/rust-overlay/8ec8a5a41f8d8244e672829c9cd705416139d3f0";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, lean4-nix, rust-overlay, ... }:
    let
      systems = [ "aarch64-darwin" "x86_64-darwin" "aarch64-linux" "x86_64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      pkgsFor = system: import nixpkgs {
        inherit system;
        overlays = [
          (import ./nix/angr)
          (lean4-nix.readToolchainFile {
            toolchain = ./lean-toolchain;
            binary = true;
          })
          rust-overlay.overlays.default
          (import ./nix/cosmic-ray)
        ];
      };
      pythonFor = system:
        let pkgs = pkgsFor system;
        in pkgs.python312.withPackages (ps: [
          ps.angr
          ps.cosmic-ray
          ps.coverage
          ps.hypothesis
          ps.ipython
          ps.pytest
          ps.z3-solver
        ]);
    in {
      overlays.cosmic-ray = import ./nix/cosmic-ray;

      lib = {
        inherit lean4-nix rust-overlay;
        nixpkgsRevision = "e79d204daf01f8a877f7b2ce7324874ce9c84676";
        # Clients keep their module graphs; this closure is added to a worker
        # alongside the shared base when the client's profile is selected.
        worker = import ./nix/reapi.nix;
      };

      packages = forAllSystems (system:
        let pkgs = pkgsFor system;
        in {
          angr-python = pythonFor system;
          cosmic-ray = pkgs.python312Packages.cosmic-ray;
          exit-codes = pkgs.python312Packages.exit-codes;
        });

      devShells = forAllSystems (system:
        let
          pkgs = pkgsFor system;
          python = pythonFor system;
        in {
          default = pkgs.mkShell {
            IFRL_ANGR_ENVIRONMENT = "${python}";
            packages = [
              pkgs.bashInteractive
              pkgs.git
              pkgs.jujutsu
              pkgs.lean
              pkgs.ruff
              pkgs.rust-bin.stable."1.95.0".default
              pkgs.z3
              python
              (import ./nix/bazel.nix { inherit pkgs; })
            ];
          };
        });
    };
}
