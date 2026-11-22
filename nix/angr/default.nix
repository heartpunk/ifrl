_final: prev: {
  pythonPackagesExtensions = prev.pythonPackagesExtensions ++ [
    (_pythonFinal: pythonPrev: {
      pyvex = pythonPrev.pyvex.overridePythonAttrs (old: {
        patches = (old.patches or [ ]) ++ [
          # Temporary backport until the pinned PyVEX includes this fix:
          # https://github.com/angr/vex/pull/107
          ./patches/vex-cmpxchg-preserve-rax.patch
        ];
      });
    })
  ];
}
