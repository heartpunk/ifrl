{
  description = "Izom native anti-unification and trace recovery";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/e7a3ca8092b61ff85b6a45bf863ea2b2d6a661b3";
  outputs = { nixpkgs, ... }:
    let systems = [ "aarch64-darwin" "x86_64-darwin" "aarch64-linux" "x86_64-linux" ];
    in { devShells = nixpkgs.lib.genAttrs systems (system:
      let pkgs = import nixpkgs { inherit system; };
      in { default = pkgs.mkShell { packages = [ pkgs.elan ]; }; }); };
}
