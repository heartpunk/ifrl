{
  description = "Shared suite Nix dependencies and Bazel worker infrastructure";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/e7a3ca8092b61ff85b6a45bf863ea2b2d6a661b3";
    angr-nix = {
      url = "github:heartpunk/angr-nix/1c679a68f0761ba24d14abae5e30283fa090a1db";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    lean4-nix = {
      url = "github:heartpunk/lean4-nix/016ac348e901dc8d924c0d768a5ca9aee86e1763";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    rust-overlay = {
      url = "github:oxalica/rust-overlay/8ec8a5a41f8d8244e672829c9cd705416139d3f0";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, angr-nix, lean4-nix, rust-overlay, ... }:
    let
      systems = [ "aarch64-darwin" "x86_64-darwin" "aarch64-linux" "x86_64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      pkgsFor = system: import nixpkgs {
        inherit system;
        overlays = [
          (lean4-nix.readToolchainFile {
            toolchain = ./lean-toolchain;
            binary = true;
          })
          rust-overlay.overlays.default
        ];
      };
    in {
      lib = {
        inherit angr-nix lean4-nix rust-overlay;
        nixpkgsRevision = "e7a3ca8092b61ff85b6a45bf863ea2b2d6a661b3";
        # Clients keep their module graphs; this closure is added to a worker
        # alongside the shared base when the client's profile is selected.
        worker = import ./nix/reapi.nix;
      };

      devShells = forAllSystems (system:
        let pkgs = pkgsFor system;
        in {
          default = pkgs.mkShell {
            IFRL_ANGR_ENVIRONMENT = "${angr-nix.packages.${system}.default}";
            packages = [
              pkgs.bashInteractive
              pkgs.git
              pkgs.jujutsu
              pkgs.python312
              pkgs.lean
              pkgs.rust-bin.stable."1.95.0".default
              pkgs.z3
              angr-nix.packages.${system}.default
              (import ./nix/bazel.nix { inherit pkgs; })
            ];
          };
        });
    };
}
