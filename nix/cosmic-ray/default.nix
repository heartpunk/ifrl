# Python package overlay kept self-contained so these package expressions can
# later move into a standalone flake or Nixpkgs with minimal changes.
final: prev:
{
  python312 = prev.python312.override (old: {
    packageOverrides = prev.lib.composeExtensions
      (old.packageOverrides or (_: _: { }))
      (pythonFinal: _pythonPrev: {
        exit-codes = pythonFinal.callPackage ./exit-codes.nix { };
        cosmic-ray = pythonFinal.callPackage ./cosmic-ray.nix { };
      });
  });
}
