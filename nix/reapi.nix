{ pkgs
, python
, developmentLauncher
, component
, workerContract
, contractProperty ? "${component}-nix-contract"
, endpointEnvironment ? "IFRL_REAPI_ENDPOINT"
, workerCpuCount ? 2
, workerMemoryMb ? 4096
, nativelink ? import ./nativelink.nix { inherit pkgs; }
}:
let
  entrypoint = pkgs.writeShellScript "ifrl-action-entrypoint" ''
    exec ${pkgs.util-linux}/bin/unshare --user --map-current-user --mount \
      --pid --fork --mount-proc --kill-child -- "$@"
  '';
in pkgs.writeShellScriptBin "${component}-reapi" ''
  exec ${developmentLauncher} ${python}/bin/python ${../python/ifrl/reapi.py} \
    --nativelink ${nativelink}/bin/nativelink \
    --entrypoint ${entrypoint} \
    --component ${component} \
    --contract-property ${contractProperty} \
    --worker-contract ${workerContract} \
    --endpoint-environment ${endpointEnvironment} \
    --worker-cpu-count ${toString workerCpuCount} \
    --worker-memory-mb ${toString workerMemoryMb} "$@"
''
