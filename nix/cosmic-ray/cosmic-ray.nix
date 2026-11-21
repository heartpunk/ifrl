{ buildPythonPackage
, src
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
  version = "0.0.0+unstable.${src.shortRev or "dirty"}";
in buildPythonPackage {
  inherit pname version;
  pyproject = true;

  inherit src;
  env.SETUPTOOLS_SCM_PRETEND_VERSION = version;

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
