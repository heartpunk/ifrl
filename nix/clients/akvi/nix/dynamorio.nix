{ stdenv, fetchurl, autoPatchelfHook, zlib, libunwind, gcc-unwrapped, snappy, lz4, xxHash }:

stdenv.mkDerivation rec {
  pname = "dynamorio";
  version = "11.91.20722";

  src = fetchurl {
    url = "https://github.com/DynamoRIO/dynamorio/releases/download/cronbuild-${version}/DynamoRIO-Linux-${version}.tar.gz";
    sha256 = "c183fa240903b277658f153eec32d3b2ab5cee3075e6892f606453e5f31dc803";
  };

  nativeBuildInputs = [ autoPatchelfHook ];
  buildInputs = [ zlib libunwind gcc-unwrapped.lib snappy lz4 xxHash ];

  # DynamoRIO is pre-built, no compilation needed
  dontBuild = true;
  dontConfigure = true;

  installPhase = ''
    mkdir -p $out
    cp -r * $out/

    # Make sure drrun is in PATH
    mkdir -p $out/bin
    ln -s $out/bin64/drrun $out/bin/drrun || true
  '';

  meta = {
    description = "Dynamic binary instrumentation framework";
    homepage = "https://dynamorio.org/";
    platforms = [ "x86_64-linux" ];
  };
}
