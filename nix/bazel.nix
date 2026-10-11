{ pkgs }:
let
  version = "9.1.1";
in
if pkgs.stdenv.isDarwin then pkgs.stdenvNoCC.mkDerivation {
  pname = "bazel";
  inherit version;
  src = pkgs.fetchurl {
    url = "https://github.com/bazelbuild/bazel/releases/download/${version}/bazel-${version}-darwin-arm64";
    hash = "sha256-LbiDcYRT8EN6e8tAjoidv4U5zcTWHI68OAehqI0C/wg=";
  };
  dontUnpack = true;
  dontFixup = true;
  installPhase = ''
    install -Dm755 "$src" "$out/bin/bazel"
  '';
} else pkgs.bazel_9
