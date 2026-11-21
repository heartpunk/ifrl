{
  description = "Izom native anti-unification and trace recovery";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/master";
  outputs = { nixpkgs, ... }:
    let systems = [ "aarch64-darwin" "x86_64-darwin" "aarch64-linux" "x86_64-linux" ];
    in { devShells = nixpkgs.lib.genAttrs systems (system:
      let pkgs = import nixpkgs { inherit system; };
      in { default = pkgs.mkShell { packages = [ pkgs.elan ]; }; }); };
}
