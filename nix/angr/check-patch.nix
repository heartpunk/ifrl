{ pkgs }:
let
  patchCheck = pkgs.runCommand "ifrl-angr-fp-smt-significand-patch-check" {
    nativeBuildInputs = [ pkgs.patch ];
  } ''
    mkdir source
    cp -R ${pkgs.python312Packages.angr.src}/. source/
    cd source
    if patch --dry-run --batch --forward -p1 < ${./fp-smt-significand.patch}; then
      printf apply > "$out"
    else
      printf stock > "$out"
    fi
  '';
in
builtins.readFile patchCheck == "apply"
