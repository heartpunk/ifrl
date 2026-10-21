{ buildPythonPackage
, fetchurl
, lib
, hatchling
, hatch-vcs
, aiohttp
, anybadge
, attrs
, click
, decorator
, exit-codes
, gitpython
, parso
, rich
, sqlalchemy
, stevedore
, toml
, yattag
}:

let
  pname = "cosmic-ray";
  version = "8.7.0";
in buildPythonPackage {
  inherit pname version;
  pyproject = true;

  src = fetchurl {
    url = "https://files.pythonhosted.org/packages/b7/44/0f033f653a859f82efb8b72edfa3dd3feba30f94b1784c74149908d9bbfd/cosmic_ray-8.7.0.tar.gz";
    hash = "sha256-8ejNvZuMnZFFvCs3JHCBtCPR4HnZKaPaMHFLI9QLSnA=";
  };

  build-system = [ hatchling hatch-vcs ];
  dependencies = [
    aiohttp
    anybadge
    attrs
    click
    decorator
    exit-codes
    gitpython
    parso
    rich
    sqlalchemy
    stevedore
    toml
    yattag
  ];

  doCheck = false;
  pythonImportsCheck = [ "cosmic_ray" ];

  meta = {
    description = "Mutation testing for Python";
    homepage = "https://github.com/sixty-north/cosmic-ray";
    license = lib.licenses.mit;
    mainProgram = "cosmic-ray";
    platforms = lib.platforms.all;
  };
}
