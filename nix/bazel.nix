{ pkgs }:
let
  version = "9.2.0";
in
if pkgs.stdenv.isDarwin then pkgs.stdenvNoCC.mkDerivation {
  pname = "bazel";
  inherit version;
  src = pkgs.fetchurl {
    url = "https://github.com/bazelbuild/bazel/releases/download/${version}/bazel-${version}-darwin-arm64";
    hash = "sha256-3UZjUqPk01gbiJh0DuH/IIhmzL4l+NNnxdy5UCGVh+Y=";
  };
  dontUnpack = true;
  dontFixup = true;
  installPhase = ''
    install -Dm755 "$src" "$out/bin/bazel"
  '';
} else pkgs.bazel_9
