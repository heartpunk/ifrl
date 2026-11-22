{
  description = "Shared suite Nix dependencies and Bazel worker infrastructure";

  inputs = {
    cosmic-ray-src = { url = "github:sixty-north/cosmic-ray/master"; flake = false; };
    exit-codes-src = { url = "github:sixty-north/exit-codes/master"; flake = false; };
    nixpkgs.url = "github:NixOS/nixpkgs/master";
    lean4-nix = {
      url = "github:heartpunk/lean4-nix/main";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    rust-overlay = {
      url = "github:oxalica/rust-overlay/master";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, lean4-nix, rust-overlay, cosmic-ray-src, exit-codes-src, ... }:
    let
      systems = [ "aarch64-darwin" "x86_64-darwin" "aarch64-linux" "x86_64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      # Preserve the exported overlay for consumers; the locked Angr includes the upstream fix.
      angrOverlay = _final: _prev: { };
      cosmicRayOverlay = import ./nix/cosmic-ray { inherit cosmic-ray-src exit-codes-src; };
      pkgsFor = system: import nixpkgs {
        inherit system;
        overlays = [
          angrOverlay
          (lean4-nix.readToolchainFile {
            toolchain = ./lean-toolchain;
            binary = true;
          })
          rust-overlay.overlays.default
          cosmicRayOverlay
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
      overlays.angr = angrOverlay;
      overlays.cosmic-ray = cosmicRayOverlay;

      lib = {
        inherit lean4-nix rust-overlay;
        nixpkgsRevision = nixpkgs.rev or nixpkgs.dirtyRev or "dirty";
        # Clients keep their module graphs; this closure is added to a worker
        # alongside the shared base when the client's profile is selected.
        worker = import ./nix/reapi.nix;
      };

      packages = forAllSystems (system:
        let pkgs = pkgsFor system;
        in {
          actionlint = pkgs.actionlint;
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
            IFRL_AST_GREP = "${pkgs.ast-grep}/bin/ast-grep";
            IFRL_TREE_SITTER_LEAN_PARSER = "${pkgs.tree-sitter-grammars.tree-sitter-lean}/parser";
            packages = [
              pkgs.ast-grep
              pkgs.bashInteractive
              pkgs.git
              pkgs.jujutsu
              pkgs.lean
              pkgs.ruff
              pkgs.rust-bin.stable."1.95.0".default
              pkgs.tree-sitter-grammars.tree-sitter-lean
              pkgs.z3
              python
              (import ./nix/bazel.nix { inherit pkgs; })
            ];
          };
        });
    };
}
