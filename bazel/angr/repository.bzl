"""Make the shared, patched Nix Angr package a declared Bazel Python input."""

_ROOT_ENV = "IFRL_ANGR_ROOT"

def _impl(ctx):
    root = ctx.os.environ.get(_ROOT_ENV)
    if not root or not root.startswith("/nix/store/"):
        fail("{} must name the Angr package supplied by IFRL".format(_ROOT_ENV))
    site = ctx.path(root + "/lib/python3.12/site-packages")
    if not site.get_child("angr/__init__.py").exists:
        fail("{} does not contain Angr for Python 3.12".format(root))
    ctx.symlink(site, "site-packages")
    ctx.file("BUILD.bazel", """\
load("@rules_python//python:defs.bzl", "py_library")
py_library(
    name = "pkg",
    srcs = glob(["site-packages/angr/**/*.py"]),
    data = glob(
        ["site-packages/angr/**/*", "site-packages/angr-*.dist-info/**/*"],
        exclude = ["**/*.py", "**/__pycache__/**"],
    ),
    imports = ["site-packages"],
    deps = %s,
    visibility = ["//visibility:public"],
)
""" % repr(ctx.attr.deps))

angr_repository = repository_rule(
    implementation = _impl,
    attrs = {"deps": attr.string_list(mandatory = True)},
    environ = [_ROOT_ENV],
    configure = True,
    local = True,
)
