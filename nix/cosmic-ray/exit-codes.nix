{ buildPythonPackage
, fetchurl
, lib
, setuptools
}:

let
  pname = "exit-codes";
  version = "1.3.0";
in buildPythonPackage {
  inherit pname version;
  pyproject = true;

  src = fetchurl {
    url = "https://files.pythonhosted.org/packages/f8/20/1a8671601b459a8388185ee29f98cee5965a94aeaccc6b9c926f4afec4dc/exit_codes-1.3.0.tar.gz";
    hash = "sha256-j+OgVr5svFMNWdmtm9wXcdjP99msc4agw5tReorlKz4=";
  };

  build-system = [ setuptools ];
  pythonImportsCheck = [ "exit_codes" ];

  meta = {
    description = "Platform-independent exit codes for Python";
    homepage = "https://github.com/sixty-north/exit-codes";
    license = lib.licenses.mit;
  };
}
