{
  description = "Concrete trace investigation development tools";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/e7a3ca8092b61ff85b6a45bf863ea2b2d6a661b3";
  inputs.rust-overlay = { url = "github:oxalica/rust-overlay"; inputs.nixpkgs.follows = "nixpkgs"; };
  outputs = { nixpkgs, rust-overlay, ... }:
    let systems = [ "x86_64-linux" "aarch64-darwin" ];
    in { devShells = nixpkgs.lib.genAttrs systems (system:
      let pkgs = import nixpkgs { inherit system; overlays = [ rust-overlay.overlays.default ]; };
      in { default = pkgs.mkShell {
        packages = [ pkgs.python3 pkgs.elan pkgs.rust-bin.stable."1.95.0".default pkgs.cmake pkgs.gcc pkgs.pkg-config pkgs.git pkgs.rsync pkgs.binutils pkgs.perl ] ++ pkgs.lib.optionals pkgs.stdenv.isLinux [ (pkgs.callPackage ./nix/dynamorio.nix {}) ];
        shellHook = ''
          toolchain="$HOME/.elan/toolchains/leanprover--lean4---v4.34.1"
          if [ ! -x "$toolchain/bin/lean" ]; then
            elan toolchain install leanprover/lean4:v4.34.1 || return 1
          fi
          export PATH="$toolchain/bin:$PATH"
          export LEAN_NUM_THREADS=4
          ${if pkgs.stdenv.isLinux then "export DYNAMORIO_DIR=${pkgs.callPackage ./nix/dynamorio.nix {}}" else ""}
        '';
      }; }); };
}
