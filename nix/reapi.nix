# Common NativeLink/REAPI package constructor. Callers supply the shared
# development environment and the client's extra Nix closure.
{ pkgs
, python
, developmentEnvironment
, component
, workerContract
, clientDependencies ? pkgs.emptyDirectory
, contractProperty ? "${component}-nix-contract"
, endpointEnvironment ? "IFRL_REAPI_ENDPOINT"
, workerCpuCount ? 2
, workerMemoryMb ? 4096
, nativelink ? import ./nativelink.nix { inherit pkgs; }
}:
let
  entrypoint = pkgs.writeShellScript "ifrl-action-entrypoint" ''
    export IFRL_CLIENT_DEPENDENCIES=${clientDependencies}
    export PATH=${clientDependencies}/bin:$PATH
    exec ${pkgs.util-linux}/bin/unshare --user --map-current-user --mount \
      --pid --fork --mount-proc --kill-child -- "$@"
  '';
  pythonEntrypoint = ./../python/ifrl/reapi.py;
in pkgs.writeShellScriptBin "${component}-reapi" ''
  export IFRL_CLIENT_DEPENDENCIES=${clientDependencies}
  export PATH=${pkgs.lib.makeBinPath [ developmentEnvironment clientDependencies ]}:$PATH
  exec ${developmentEnvironment}/bin/${component}-dev ${python}/bin/python ${pythonEntrypoint} \
    --nativelink ${nativelink}/bin/nativelink \
    --entrypoint ${entrypoint} \
    --component ${component} \
    --contract-property ${contractProperty} \
    --worker-contract ${workerContract} \
    --endpoint-environment ${endpointEnvironment} \
    --worker-cpu-count ${toString workerCpuCount} \
    --worker-memory-mb ${toString workerMemoryMb} \
    --client-dependencies ${clientDependencies} "$@"
''
