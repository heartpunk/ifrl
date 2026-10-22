#!/usr/bin/env python3
"""Inventory and compare source references across explicitly selected repos.

The in-memory records use Dublin Core terms for document metadata and PROV-O
terms for entity/activity provenance. The checker itself only reports results.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

SUITE_COMPONENTS = frozenset({"ifrl", "ayxg", "ixyk", "wruh", "utem", "ufda"})
IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".jj",
        ".lake",
        ".direnv",
        ".devenv",
        ".pytest_cache",
        "__pycache__",
        "node_modules",
        "target",
        "dist",
        "result",
    }
)
BUILD_FILES = {
    "flake.nix": ("nix", "application/nix"),
    "flake.lock": ("json", "application/json"),
    "MODULE.bazel": ("python", "text/x-starlark"),
    "MODULE.bazel.lock": ("json", "application/json"),
    "WORKSPACE": ("python", "text/x-starlark"),
    "WORKSPACE.bazel": ("python", "text/x-starlark"),
    "lakefile.lean": ("lean", "text/x-lean"),
    "lake-manifest.json": ("json", "application/json"),
    "lean-toolchain": ("plain", "text/plain"),
}


@dataclass(frozen=True)
class Repository:
    """A PROV-O entity for an explicitly selected source checkout."""

    name: str
    root: Path

    @property
    def identifier(self) -> str:
        return f"urn:ifrl:repository:{self.name}"


@dataclass(frozen=True)
class SourceDocument:
    """A PROV-O entity with DCMI identifier, title, language, and format terms."""

    repository: str
    path: str
    language: str
    format: str

    @property
    def identifier(self) -> str:
        return f"{self.repository}/{self.path}"

    @property
    def title(self) -> str:
        return Path(self.path).name


@dataclass(frozen=True)
class SourceLocation:
    start_line: int | None = None
    start_column: int | None = None
    end_line: int | None = None
    end_column: int | None = None
    json_pointer: str | None = None


@dataclass(frozen=True)
class SourceReference:
    """A PROV-O entity derived from one source document and source location."""

    identifier: str
    was_derived_from: SourceDocument
    at_location: SourceLocation
    kind: str
    target_repository: str | None
    input_name: str | None
    raw_value: str
    selector: str | None = None
    revision: str | None = None
    lock_node: str | None = None


@dataclass(frozen=True)
class Finding:
    """A PROV-O entity derived from the source-reference evidence it evaluates."""

    status: str
    rule: str
    summary: str

    was_derived_from: tuple[SourceReference, ...]

    @property
    def identifier(self) -> str:
        evidence = "\0".join(item.identifier for item in self.was_derived_from)
        identity = f"{self.status}\0{self.rule}\0{evidence}"
        return "urn:ifrl:suite-reference-finding:" + hashlib.sha256(identity.encode()).hexdigest()


@dataclass(frozen=True)
class AuditActivity:
    """A PROV-O activity with explicit used and generated entity relationships."""

    identifier: str
    used: tuple[Repository | SourceDocument | SourceReference, ...]
    generated: tuple[SourceDocument | SourceReference | Finding, ...]


def parse_repository(value: str) -> Repository:
    try:
        name, raw_path = value.split("=", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected NAME=PATH") from error
    root = Path(raw_path).expanduser().resolve()
    if not name or not root.is_dir():
        raise argparse.ArgumentTypeError(f"invalid repository root: {value}")
    return Repository(name=name, root=root)


def enumerate_build_files(repositories: Iterable[Repository]) -> tuple[SourceDocument, ...]:
    """Find known manifests under the supplied roots; do not discover roots."""
    documents: list[SourceDocument] = []
    for repository in repositories:
        for directory, subdirectories, filenames in os.walk(repository.root):
            subdirectories[:] = sorted(
                name
                for name in subdirectories
                if name not in IGNORED_DIRECTORIES
                and not name.startswith("bazel-")
            )
            base = Path(directory)
            for filename in sorted(filenames):
                relative = (base / filename).relative_to(repository.root)
                if filename in BUILD_FILES:
                    language, media_type = BUILD_FILES[filename]
                elif (
                    relative.parts[:2] == (".github", "workflows")
                    and Path(filename).suffix in {".yml", ".yaml"}
                ):
                    language, media_type = "yaml", "application/yaml"
                else:
                    continue
                documents.append(
                    SourceDocument(
                        repository=repository.name,
                        path=relative.as_posix(),
                        language=language,
                        format=media_type,
                    )
                )
    return tuple(sorted(documents, key=lambda item: item.identifier))


class AstGrep:
    def __init__(self) -> None:
        self.executable = os.environ.get("IFRL_AST_GREP") or shutil.which("ast-grep")
        self.lean_parser = os.environ.get("IFRL_TREE_SITTER_LEAN_PARSER")
        self._config_directory: tempfile.TemporaryDirectory[str] | None = None
        self._lean_config: Path | None = None
        if not self.executable:
            raise RuntimeError("ast-grep is missing; run this from the IFRL flake dev shell")

    def close(self) -> None:
        if self._config_directory is not None:
            self._config_directory.cleanup()

    def _config_for_lean(self) -> Path:
        if self._lean_config is not None:
            return self._lean_config
        if not self.lean_parser or not Path(self.lean_parser).is_file():
            raise RuntimeError(
                "the experimental Lean Tree-sitter parser is missing; "
                "run this from the IFRL flake dev shell"
            )
        self._config_directory = tempfile.TemporaryDirectory(prefix="ifrl-suite-refs-")
        self._lean_config = Path(self._config_directory.name) / "sgconfig.yml"
        self._lean_config.write_text(
            "customLanguages:\n"
            "  lean:\n"
            f"    libraryPath: {json.dumps(self.lean_parser)}\n"
            "    extensions: [lean]\n"
            "    expandoChar: _\n",
            encoding="utf-8",
        )
        return self._lean_config

    def find(self, document: SourceDocument, root: Path, pattern: str) -> list[dict]:
        command = [self.executable, "run", "--lang", document.language]
        if document.language == "lean":
            command.extend(
                [
                    "--config",
                    str(self._config_for_lean()),
                    "--custom-languages",
                    "allow",
                ]
            )
        command.extend(
            ["--pattern", pattern, "--json=compact", str(root / document.path)]
        )
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode == 1 and result.stdout.strip() == "[]":
            return []
        if result.returncode != 0:
            details = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(
                f"ast-grep failed for {document.identifier}: {details or result.returncode}"
            )
        try:
            parsed = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"ast-grep returned invalid JSON for {document.identifier}"
            ) from error
        if not isinstance(parsed, list):
            raise TypeError(f"ast-grep returned a non-list for {document.identifier}")
        return parsed


def match_location(match: dict) -> SourceLocation:
    start = match.get("range", {}).get("start", {})
    end = match.get("range", {}).get("end", {})
    return SourceLocation(
        start_line=start.get("line"),
        start_column=start.get("column"),
        end_line=end.get("line"),
        end_column=end.get("column"),
    )


def capture_location(match: dict, name: str) -> SourceLocation:
    capture = match.get("metaVariables", {}).get("single", {}).get(name, {})
    location = capture.get("range", {})
    start = location.get("start", {})
    end = location.get("end", {})
    return SourceLocation(
        start_line=start.get("line"),
        start_column=start.get("column"),
        end_line=end.get("line"),
        end_column=end.get("column"),
    )


def captures(match: dict) -> dict[str, str]:
    single = match.get("metaVariables", {}).get("single", {})
    return {name: value.get("text", "") for name, value in single.items()}


def decode_string_literal(raw: str) -> str | None:
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"'):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, str) else None
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    return None


def parse_source_url(value: str | None) -> tuple[str | None, str | None]:
    """Return normalized owner/repository and declared selector, when static."""
    if not value:
        return None, None
    if value.startswith("github:"):
        source = value.removeprefix("github:")
        path, _, query = source.partition("?")
        parts = path.strip("/").split("/")
        if len(parts) < 2:
            return None, None
        owner, repository = parts[0], parts[1].removesuffix(".git")
        query_ref = parse_qs(query).get("ref", [None])[0]
        selector = query_ref or (unquote(parts[2]) if len(parts) > 2 else None)
        return f"{owner}/{repository}", selector

    normalized = value.removeprefix("git+")
    parsed = urlsplit(normalized)
    if parsed.hostname and parsed.path:
        parts = [unquote(part) for part in parsed.path.strip("/").split("/")]
        if len(parts) < 2:
            return None, None
        owner, repository = parts[0], parts[1].removesuffix(".git")
        query = parse_qs(parsed.query)
        selector = (
            query.get("ref", [None])[0]
            or query.get("rev", [None])[0]
            or (unquote(parsed.fragment) if parsed.fragment else None)
        )
        return f"{owner}/{repository}", selector
    return None, None


def reference(
    document: SourceDocument,
    location: SourceLocation,
    kind: str,
    target: str | None,
    input_name: str | None,
    raw_value: str,
    selector: str | None = None,
    revision: str | None = None,
    lock_node: str | None = None,
) -> SourceReference:
    source = "\0".join(
        [
            document.identifier,
            str(location.start_line),
            str(location.json_pointer),
            kind,
            target or "",
            raw_value,
        ]
    )
    return SourceReference(
        identifier="urn:ifrl:source-reference:" + hashlib.sha256(source.encode()).hexdigest(),
        was_derived_from=document,
        at_location=location,
        kind=kind,
        target_repository=target,
        input_name=input_name,
        raw_value=raw_value,
        selector=selector,
        revision=revision,
        lock_node=lock_node,
    )


def extract_flake_declarations(
    document: SourceDocument, root: Path, ast_grep: AstGrep
) -> list[SourceReference]:
    patterns = [
        ("{ url = $URL; $$$REST }", None),
        ("{ description = $DESCRIPTION; inputs.$NAME.url = $URL; $$$REST }", None),
        ("{ inputs.$NAME.url = $URL; $$$REST }", None),
    ]
    # Nix also permits dotted attributes inside an input set, for example
    # `ifrl.url = ...`; retain that syntax as source evidence too.
    patterns.extend(
        (f"{{ {name}.url = $URL; $$$REST }}", name)
        for name in sorted(SUITE_COMPONENTS)
    )
    found: dict[str, SourceReference] = {}
    for pattern, fixed_input_name in patterns:
        for match in ast_grep.find(document, root, pattern):
            values = captures(match)
            raw = values.get("URL", "")
            value = decode_string_literal(raw)
            target, selector = parse_source_url(value)
            if target is None:
                # A dotted suite input still identifies its target if its
                # URL expression is dynamic; preserve it as unresolved evidence.
                for name in SUITE_COMPONENTS:
                    if f"{name}.url" in match.get("text", ""):
                        target = f"heartpunk/{name}"
                        break
            if target is None:
                continue
            revision = selector if selector and re.fullmatch(r"[0-9a-fA-F]{40}", selector) else None
            item = reference(
                document,
                capture_location(match, "URL"),
                "flake-input-declaration",
                target,
                values.get("NAME") or fixed_input_name,
                value if value is not None else raw,
                selector,
                revision,
            )
            found[item.identifier] = item
    return list(found.values())


def extract_lockfile(
    document: SourceDocument, root: Path
) -> list[SourceReference]:
    data = json.loads((root / document.path).read_text(encoding="utf-8"))
    result: list[SourceReference] = []

    if document.path.endswith("flake.lock"):
        nodes = data.get("nodes", {})
        direct_inputs = {
            node_name: input_name
            for input_name, node_name in nodes.get("root", {}).get("inputs", {}).items()
            if isinstance(node_name, str)
        }
        for name, node in nodes.items():
            locked = node.get("locked", {})
            owner, repository, revision = (
                locked.get("owner"),
                locked.get("repo"),
                locked.get("rev"),
            )
            if not (owner and repository and revision):
                continue
            original = node.get("original", {})
            selector = original.get("ref") or original.get("rev")
            result.append(
                reference(
                    document,
                    SourceLocation(json_pointer=f"/nodes/{name}/locked"),
                    "nix-flake-lock-resolution",
                    f"{owner}/{repository}",
                    direct_inputs.get(name),
                    str(revision),
                    selector,
                    str(revision),
                    lock_node=name,
                )
            )
        return result

    if document.path.endswith("lake-manifest.json"):
        for index, package in enumerate(data.get("packages", [])):
            name = package.get("name")
            if not name:
                continue
            url = package.get("url") or package.get("git")
            target, selector_from_url = parse_source_url(url)
            if target is None and name in SUITE_COMPONENTS:
                target = f"heartpunk/{name}"
            revision = package.get("rev")
            selector = package.get("inputRev") or selector_from_url
            if target is None:
                continue
            result.append(
                reference(
                    document,
                    SourceLocation(json_pointer=f"/packages/{index}"),
                    "lake-manifest-resolution",
                    target,
                    str(name),
                    str(url or name),
                    str(selector) if selector is not None else None,
                    str(revision) if revision is not None else None,
                )
            )
        return result

    # Bazel lock files have evolved; retain the document for discovery now,
    # while source revisions remain extracted from its AST declaration.
    return result


def extract_lean_toolchain(document: SourceDocument, root: Path) -> list[SourceReference]:
    selector = (root / document.path).read_text(encoding="utf-8").strip()
    if not selector:
        return []
    return [
        reference(
            document,
            SourceLocation(start_line=1, start_column=1),
            "lean-toolchain-selector",
            "leanprover/lean4",
            None,
            selector,
            selector,
        )
    ]


def extract_bazel_overrides(
    document: SourceDocument, root: Path, ast_grep: AstGrep
) -> list[SourceReference]:
    result: list[SourceReference] = []
    for match in ast_grep.find(document, root, "git_override($$$ARGS)"):
        try:
            call = ast.parse(match["text"], mode="eval").body
        except (SyntaxError, KeyError):
            result.append(
                reference(
                    document,
                    match_location(match),
                    "bazel-git-override-unparsed",
                    None,
                    None,
                    match.get("text", ""),
                )
            )
            continue
        if not isinstance(call, ast.Call):
            continue
        fields = {keyword.arg: keyword.value for keyword in call.keywords if keyword.arg}
        module = fields.get("module_name")
        remote = fields.get("remote")
        commit = fields.get("commit")
        try:
            name = ast.literal_eval(module) if module else None
            url = ast.literal_eval(remote) if remote else None
            revision = ast.literal_eval(commit) if commit else None
        except (ValueError, TypeError):
            name, url, revision = None, None, None
        target, selector = parse_source_url(url if isinstance(url, str) else None)
        if target is None and isinstance(name, str) and name in SUITE_COMPONENTS:
            target = f"heartpunk/{name}"
        result.append(
            reference(
                document,
                match_location(match),
                "bazel-git-override",
                target,
                str(name) if name is not None else None,
                match.get("text", ""),
                str(selector) if selector is not None else None,
                str(revision) if revision is not None else None,
            )
        )
    return result


def extract_lake_requirements(
    document: SourceDocument, root: Path, ast_grep: AstGrep
) -> list[SourceReference]:
    result: list[SourceReference] = []
    patterns = [
        "require _NAME from git _URL @ _REV",
        "require _NAME from _SOURCE",
    ]
    seen: set[tuple[int | None, str]] = set()
    for pattern in patterns:
        for match in ast_grep.find(document, root, pattern):
            values = captures(match)
            name = decode_string_literal(values.get("NAME", "")) or values.get("NAME")
            if not name:
                continue
            source = values.get("URL") or values.get("SOURCE", "")
            revision_raw = values.get("REV", "")
            location = match_location(match)
            key = (location.start_line, name)
            if key in seen:
                continue
            seen.add(key)
            url = decode_string_literal(source)
            target, selector_from_url = parse_source_url(url)
            if target is None and name in SUITE_COMPONENTS:
                target = f"heartpunk/{name}"
            selector_value = decode_string_literal(revision_raw) or revision_raw or selector_from_url
            revision = (
                selector_value
                if selector_value and re.fullmatch(r"[0-9a-fA-F]{40}", selector_value)
                else None
            )
            result.append(
                reference(
                    document,
                    capture_location(match, "REV")
                    if revision_raw
                    else capture_location(match, "SOURCE"),
                    "lake-requirement",
                    target,
                    name,
                    source,
                    selector_value,
                    revision,
                )
            )
    return result


def extract_workflow_references(
    document: SourceDocument, root: Path, ast_grep: AstGrep
) -> list[SourceReference]:
    result: list[SourceReference] = []
    for match in ast_grep.find(document, root, "uses: $REF"):
        raw = captures(match).get("REF", "").strip("'\" ")
        if raw.startswith(("./", "docker://")):
            continue
        action, separator, selector = raw.partition("@")
        parts = action.split("/")
        if len(parts) < 2:
            continue
        target = f"{parts[0]}/{parts[1]}"
        result.append(
            reference(
                document,
                match_location(match),
                "workflow-action-or-reusable-workflow",
                target,
                None,
                raw,
                selector if separator else None,
                selector if separator and re.fullmatch(r"[0-9a-fA-F]{40}", selector) else None,
            )
        )

    checkout_pattern = "with:\n  repository: $REPOSITORY\n  ref: $REF"
    for match in ast_grep.find(document, root, checkout_pattern):
        values = captures(match)
        target = values.get("REPOSITORY", "")
        if "/" not in target:
            continue
        selector = values.get("REF", "").strip("'\" ")
        result.append(
            reference(
                document,
                match_location(match),
                "workflow-checkout-source",
                target,
                None,
                match.get("text", ""),
                selector,
                selector if re.fullmatch(r"[0-9a-fA-F]{40}", selector) else None,
            )
        )
    return result


def extract_references(
    repositories: Iterable[Repository], documents: tuple[SourceDocument, ...], ast_grep: AstGrep
) -> tuple[SourceReference, ...]:
    """Extract AST-backed declarations and structurally parsed lock entries."""
    roots = {repository.name: repository.root for repository in repositories}
    result: list[SourceReference] = []
    for document in documents:
        root = roots[document.repository]
        if document.path == "flake.nix":
            result.extend(extract_flake_declarations(document, root, ast_grep))
        elif document.path.endswith(("flake.lock", "lake-manifest.json", "MODULE.bazel.lock")):
            result.extend(extract_lockfile(document, root))
        elif document.path in {"MODULE.bazel", "WORKSPACE", "WORKSPACE.bazel"}:
            result.extend(extract_bazel_overrides(document, root, ast_grep))
        elif document.path == "lean-toolchain":
            result.extend(extract_lean_toolchain(document, root))
        elif document.path.endswith("lakefile.lean"):
            result.extend(extract_lake_requirements(document, root, ast_grep))
        elif document.language == "yaml":
            result.extend(extract_workflow_references(document, root, ast_grep))
    return tuple(sorted(result, key=lambda item: item.identifier))


def evaluate_matches(
    repositories: tuple[Repository, ...], references: tuple[SourceReference, ...]
) -> tuple[Finding, ...]:
    """Compare resolved refs and declarations without executing project flakes."""
    by_document_component: dict[tuple[str, str, str], list[SourceReference]] = {}
    by_component: dict[str, list[SourceReference]] = {}
    repo_names = {repository.name for repository in repositories}
    for item in references:
        if not item.target_repository:
            continue
        by_document_component.setdefault(
            (item.was_derived_from.repository, item.was_derived_from.path, item.target_repository), []
        ).append(item)
        by_component.setdefault(item.target_repository, []).append(item)

    findings: list[Finding] = []
    shared_components = {
        item.target_repository
        for item in references
        if item.was_derived_from.repository == "ifrl"
        and item.was_derived_from.path == "flake.lock"
        and item.input_name is not None
        and item.target_repository
    }
    shared_components.update(
        component
        for component in by_component
        if component.rsplit("/", 1)[-1] in repo_names
    )

    # A single flake graph must not contain two revisions of the same source.
    lock_groups = []
    for key, items in by_document_component.items():
        direct_inputs = [item for item in items if item.input_name is not None]
        if key[1].endswith("flake.lock") and direct_inputs:
            lock_groups.append((key, direct_inputs))
    for (repo, path, component), items in lock_groups:
        revisions = {item.revision for item in items if item.revision}
        if len(revisions) > 1:
            findings.append(
                Finding(
                    "mismatch",
                    "one-lock-resolution-per-source",
                    f"{repo}/{path} resolves {component} to multiple revisions: {', '.join(sorted(revisions))}",
                    tuple(items),
                )
            )

    # IFRL's lockfile is the baseline for the dependencies it owns. Suite
    # repositories also need one common locked revision for each other suite repo.
    canonical_revisions: dict[str, str] = {}
    for component, items in by_component.items():
        canonical = {
            item.revision
            for item in items
            if item.was_derived_from.repository == "ifrl"
            and item.was_derived_from.path == "flake.lock"
            and item.input_name is not None
            and item.revision
        }
        if len(canonical) == 1:
            canonical_revisions[component] = next(iter(canonical))

    for component in sorted(shared_components):
        lock_items = [
            item
            for item in by_component.get(component, [])
            if item.was_derived_from.path == "flake.lock"
            and item.input_name is not None
            and item.revision
        ]
        if len(lock_items) < 2:
            continue
        expected = canonical_revisions.get(component)
        revisions = {item.revision for item in lock_items}
        if expected:
            mismatches = [item for item in lock_items if item.revision != expected]
            if mismatches:
                findings.append(
                    Finding(
                        "mismatch",
                        "shared-ifrl-lock-resolution",
                        f"{component} is not uniformly locked to IFRL's {expected}: "
                        + ", ".join(
                            f"{item.was_derived_from.repository}={item.revision}" for item in mismatches
                        ),
                        tuple(lock_items),
                    )
                )
        elif len(revisions) > 1:
            findings.append(
                Finding(
                    "mismatch",
                    "suite-lock-resolution",
                    f"suite lockfiles disagree on {component}: "
                    + ", ".join(
                        f"{item.was_derived_from.repository}={item.revision}"
                        for item in lock_items
                    ),
                    tuple(lock_items),
                )
            )
        else:
            findings.append(
                Finding(
                    "match",
                    "suite-lock-resolution",
                    f"suite lockfiles agree on {component} at {next(iter(revisions))}",
                    tuple(lock_items),
                )
            )

    toolchain_items = [
        item for item in references if item.kind == "lean-toolchain-selector"
    ]
    toolchains = {item.selector for item in toolchain_items}
    if toolchain_items:
        findings.append(
            Finding(
                "match" if len(toolchains) == 1 else "mismatch",
                "suite-lean-toolchain-consistency",
                "Lean toolchain selectors are " + ", ".join(sorted(toolchains)),
                tuple(toolchain_items),
            )
        )

    for item in references:
        if item.target_repository not in shared_components:
            continue
        if item.kind == "lake-requirement":
            parent = Path(item.was_derived_from.path).parent
            local_lock_path = (
                (parent / "lake-manifest.json").as_posix()
                if parent != Path(".")
                else "lake-manifest.json"
            )
        elif item.was_derived_from.path.startswith(".github/workflows/"):
            local_lock_path = "flake.lock"
        else:
            parent = Path(item.was_derived_from.path).parent
            local_lock_path = (
                (parent / "flake.lock").as_posix() if parent != Path(".") else "flake.lock"
            )
        lock_revisions = {
            candidate.revision
            for candidate in by_component.get(item.target_repository or "", [])
            if candidate.was_derived_from.repository == item.was_derived_from.repository
            and candidate.was_derived_from.path == local_lock_path
            and candidate.input_name is not None
            and candidate.revision
        }
        if item.input_name:
            lock_revisions = {
                candidate.revision
                for candidate in by_component.get(item.target_repository or "", [])
                if candidate.was_derived_from.repository == item.was_derived_from.repository
                and candidate.was_derived_from.path == local_lock_path
                and candidate.input_name == item.input_name
                and candidate.revision
            }
        if item.kind in {"flake-input-declaration", "workflow-action-or-reusable-workflow"}:
            if item.selector and "${{" not in item.selector and item.target_repository.rsplit("/", 1)[-1] in repo_names:
                status = "match" if item.selector == "main" else "mismatch"
                findings.append(
                    Finding(
                        status,
                        "suite-source-floats-on-main",
                        f"{item.was_derived_from.identifier}:{item.at_location.start_line} "
                        f"selects {item.target_repository} at {item.selector}",
                        (item,),
                    )
                )
            elif not item.selector and item.target_repository.rsplit("/", 1)[-1] in repo_names:
                findings.append(
                    Finding(
                        "unresolved",
                        "suite-source-selector",
                        f"{item.was_derived_from.identifier}:{item.at_location.start_line} "
                        f"does not state a selector for {item.target_repository}",
                        (item,),
                    )
                )
        if item.kind == "lake-requirement" and item.target_repository.rsplit("/", 1)[-1] in repo_names:
            if item.selector and "${{" not in item.selector:
                status = "match" if item.selector == "main" else "mismatch"
                findings.append(
                    Finding(
                        status,
                        "suite-source-floats-on-main",
                        f"{item.was_derived_from.identifier}:{item.at_location.start_line} "
                        f"selects {item.target_repository} at {item.selector}",
                        (item,),
                    )
                )
            elif item.revision is None:
                findings.append(
                    Finding(
                        "unresolved",
                        "lake-requirement-source",
                        f"{item.was_derived_from.identifier}:{item.at_location.start_line} "
                        f"uses a dynamic or local source expression for {item.target_repository}",
                        (item,),
                    )
                )
        if item.kind == "flake-input-declaration" and not lock_revisions:
            findings.append(
                Finding(
                    "unresolved",
                    "flake-input-has-lock-resolution",
                    f"{item.was_derived_from.identifier} declares {item.target_repository}, "
                    "but this checkout has no resolved revision for it in flake.lock",
                    (item,),
                )
            )
        elif (
            item.kind == "flake-input-declaration"
            and item.input_name is None
            and len(lock_revisions) > 1
        ):
            findings.append(
                Finding(
                    "unresolved",
                    "flake-input-ambiguous-lock-resolution",
                    f"{item.was_derived_from.identifier} declares {item.target_repository} "
                    "but does not identify which of multiple flake.lock inputs resolves it",
                    (item,),
                )
            )
        if item.revision and lock_revisions and item.revision not in lock_revisions:
            findings.append(
                Finding(
                    "mismatch",
                    "declaration-matches-lock",
                    f"{item.was_derived_from.identifier}:{item.at_location.start_line} selects "
                    f"{item.target_repository}@{item.revision}, while its flake.lock has "
                    f"{', '.join(sorted(lock_revisions))}",
                    (item,),
                )
            )
    if not references:
        findings.append(
            Finding(
                "unresolved",
                "reference-inventory-not-empty",
                "no source references were extracted from the selected build files",
                (),
            )
        )
    return tuple(findings)


def print_activity(
    discovery: AuditActivity, extraction: AuditActivity, evaluation: AuditActivity
) -> None:
    references = [item for item in extraction.generated if isinstance(item, SourceReference)]
    findings = [item for item in evaluation.generated if isinstance(item, Finding)]
    documents = [item for item in discovery.generated if isinstance(item, SourceDocument)]
    print(f"Discovered {len(documents)} build files and {len(references)} source references.")
    for finding in findings:
        refs = ", ".join(
            f"{item.was_derived_from.identifier}:{item.at_location.start_line or item.at_location.json_pointer}"
            for item in finding.was_derived_from
        )
        print(f"{finding.status.upper():10} {finding.rule}: {finding.summary}")
        if refs:
            print(f"           evidence: {refs}")
    if not findings:
        print("No suite source-reference comparisons were available.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        action="append",
        type=parse_repository,
        required=True,
        metavar="NAME=PATH",
        help="explicit checkout root; repeat for every repo to compare",
    )
    args = parser.parse_args()
    repositories = tuple(args.repo)
    names = [repository.name for repository in repositories]
    if len(names) != len(set(names)):
        parser.error("each repository name may be supplied only once")

    documents = enumerate_build_files(repositories)
    discovery = AuditActivity(f"urn:uuid:{uuid4()}", repositories, documents)
    ast_grep = AstGrep()
    try:
        references = extract_references(repositories, documents, ast_grep)
    finally:
        ast_grep.close()
    extraction = AuditActivity(f"urn:uuid:{uuid4()}", documents, references)
    findings = evaluate_matches(repositories, references)
    evaluation = AuditActivity(f"urn:uuid:{uuid4()}", references, findings)
    print_activity(discovery, extraction, evaluation)
    if any(item.status == "mismatch" for item in findings):
        return 1
    if any(item.status == "unresolved" for item in findings):
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, RuntimeError, TypeError, ValueError) as error:
        print(f"suite reference check failed: {error}", file=sys.stderr)
        raise SystemExit(2)
