final: prev:
{
  pythonPackagesExtensions = prev.pythonPackagesExtensions ++ [
    (pythonFinal: pythonPrev: {
      angr = pythonPrev.angr.overridePythonAttrs (old: {
        patches = (old.patches or [ ]) ++ [ ./fp-smt-significand.patch ];
      });
    })
  ];
}
