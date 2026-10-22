final: prev: {
  pythonPackagesExtensions = prev.pythonPackagesExtensions ++ [
    (pythonFinal: pythonPrev:
      let
        sourceBuiltAngrDeps = {
          inherit (pythonPrev) mpmath sympy pypcode grpcio pydemumble pyvex lmdb
            uefi_firmware pyxbe cle;
          "grpcio-tools" = pythonPrev."grpcio-tools";
          "patch-ng" = pythonPrev."patch-ng";
        };
        skipChecks = if prev.stdenv.hostPlatform.system == "x86_64-linux" then
          builtins.mapAttrs (_: package:
            package.overridePythonAttrs (_: { doCheck = false; })
          ) sourceBuiltAngrDeps
        else
          { };
      in
      skipChecks // {
        angr = pythonPrev.angr.overridePythonAttrs (old: {
          patches = (old.patches or [ ]) ++ [ ./fp-smt-significand.patch ];
          doCheck = false;
        });
      }
    )
  ];
}
