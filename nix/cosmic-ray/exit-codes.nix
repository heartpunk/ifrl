{ buildPythonPackage
, src
, lib
, setuptools
}:

let
  pname = "exit-codes";
  version = builtins.fromJSON (builtins.elemAt (lib.splitString " = " (builtins.head (lib.splitString "\n" (builtins.readFile "${src}/exit_codes/version.py")))) 1);
in buildPythonPackage {
  inherit pname version;
  pyproject = true;

  inherit src;

  build-system = [ setuptools ];
  pythonImportsCheck = [ "exit_codes" ];

  meta = {
    description = "Platform-independent exit codes for Python";
    homepage = "https://github.com/sixty-north/exit-codes";
    license = lib.licenses.mit;
  };
}
