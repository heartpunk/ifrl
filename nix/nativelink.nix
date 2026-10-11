{ pkgs }:
assert pkgs.stdenv.hostPlatform.system == "x86_64-linux";
pkgs.stdenvNoCC.mkDerivation {
  pname = "nativelink";
  version = "1.6.4";
  src = pkgs.fetchurl {
    url = "https://github.com/TraceMachina/nativelink/releases/download/v1.6.4/nativelink-1.6.4-x86_64-unknown-linux-musl.tar.gz";
    hash = "sha256-gfAUD30vFnyHXi7xzngl2SrIbAmzVUQal3K1d6DD870=";
  };
  sourceRoot = ".";
  installPhase = ''
    install -Dm755 "$(find . -type f -name nativelink -print -quit)" "$out/bin/nativelink"
  '';
  dontFixup = true;
}
