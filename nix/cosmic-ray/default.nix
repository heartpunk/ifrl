# Python package overlay kept self-contained so these package expressions can
# later move into a standalone flake or Nixpkgs with minimal changes.
{ cosmic-ray-src, exit-codes-src }:
final: prev:
{
  pythonPackagesExtensions = prev.pythonPackagesExtensions ++ [
    (pythonFinal: _pythonPrev: {
      exit-codes = pythonFinal.callPackage ./exit-codes.nix { src = exit-codes-src; };
      cosmic-ray = pythonFinal.callPackage ./cosmic-ray.nix { src = cosmic-ray-src; };
    })
  ];
}
