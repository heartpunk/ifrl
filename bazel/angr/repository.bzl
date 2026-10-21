"""Expose the complete Nix Angr environment as declared Bazel inputs."""

def _environment_impl(ctx):
    root = ctx.os.environ.get("IFRL_ANGR_ENVIRONMENT")
    if not root or not root.startswith("/nix/store/"):
        fail("IFRL_ANGR_ENVIRONMENT must name the complete angr-nix Python environment")
    site = ctx.path(root + "/lib/python3.12/site-packages")
    for module in ["angr", "archinfo", "cle", "pyvex", "capstone", "z3"]:
        if not site.get_child(module + "/__init__.py").exists:
            fail("IFRL_ANGR_ENVIRONMENT lacks {}".format(module))
    ctx.symlink(site, "site-packages")
    ctx.file("BUILD.bazel", """\
load("@rules_python//python:defs.bzl", "py_library")
py_library(
    name = "pkg",
    srcs = glob(["site-packages/**/*.py"]),
    precompile = "disabled",
    data = glob(
        ["site-packages/**/*"],
        exclude = ["**/*.py", "**/__pycache__/**"],
    ),
    imports = ["site-packages"],
    visibility = ["//visibility:public"],
)
""")

# The execution worker must provide the environment's Nix runtime closure:
# native libraries retain their Nix store references.
angr_environment_repository = repository_rule(
    implementation = _environment_impl,
    environ = ["IFRL_ANGR_ENVIRONMENT"],
    configure = True,
    local = True,
)
