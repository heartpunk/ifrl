"""Run existing Python checks, branch coverage, and bounded daily mutation testing."""

import argparse
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def run(command, log, timeout=600, cwd=None):
    """Bound the command and its process group, retaining output even on failure."""
    with log.open("w") as output:
        print(shlex.join(command), flush=True)
        process = subprocess.Popen(
            command, cwd=cwd, stdout=output, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            return 124


def files_for(paths):
    tracked = subprocess.check_output(["git", "ls-files", "-z"], text=True).split("\0")
    return sorted(
        path for path in tracked if path.endswith(".py")
        and any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in paths)
        and not Path(path).name.startswith("test_") and not path.endswith("_test.py")
    )


def coverage(config, report):
    from coverage import Coverage

    sources = files_for(config["sources"])
    if not sources:
        raise ValueError("Python sources were configured but no tracked files matched")
    rcfile = report / "coverage.ini"
    rcfile.write_text(
        "[run]\nbranch = true\nparallel = true\npatch = subprocess\n"
        "concurrency = multiprocessing\nsigterm = true\n"
        f"data_file = {report / 'coverage-data'}\nsource =\n    "
        + "\n    ".join(sorted({str(Path(path).parent.resolve()) for path in sources}))
        + "\n[report]\ninclude =\n    "
        + "\n    ".join(str(Path(path).resolve()) for path in sources)
        + "\nshow_missing = true\n"
    )
    codes = []
    for index, command in enumerate(config["tests"]):
        codes.append(run(
            [sys.executable, "-m", "coverage", "run", f"--rcfile={rcfile}", *command],
            report / f"tests-{index}.log", config.get("test_timeout", 600),
        ))
    cov = Coverage(config_file=str(rcfile))
    cov.combine()
    cov.save()
    cov.xml_report(outfile=str(report / "coverage.xml"))
    cov.json_report(outfile=str(report / "coverage.json"))
    cov.html_report(directory=str(report / "html"))
    with (report / "coverage.txt").open("w") as output:
        cov.report(file=output)
    write_json(report / "status.json", {"test_exit_codes": codes, "sources": sources})
    print((report / "coverage.txt").read_text())
    return int(any(codes))


def mutation(config, report):
    from contextlib import chdir

    from attrs import evolve
    from cosmic_ray.mutating import mutate_and_test
    from cosmic_ray.work_db import WorkDB, use_db
    from cosmic_ray.work_item import TestOutcome

    sources = files_for(config.get("mutation_sources", config["sources"]))
    if not sources:
        write_json(report / "status.json", {
            "status": "not-applicable",
            "reason": config["mutation_not_applicable"],
        })
        return 0
    day = datetime.now(UTC).date()
    cache = Path("ci-mutation-cache").resolve()
    cache.mkdir(exist_ok=True)
    mutant_timeout = config.get("mutation_timeout", 60)
    baseline_timeout = config.get("mutation_baseline_timeout", 60)
    budget = 900
    status = {
        "status": "incomplete", "date": str(day), "sources": sources,
        "execution_budget_seconds": budget, "per_mutant_seconds": mutant_timeout,
        "baseline_budget_seconds": baseline_timeout, "initialization_budget_seconds": 300,
    }
    write_json(report / "status.json", status)
    with tempfile.TemporaryDirectory(prefix="ifrl-mutation-") as temporary:
        work = Path(temporary)
        # Mutations never touch the checked-out sources or tests.
        tracked = subprocess.check_output(["git", "ls-files", "-z"], text=True).split("\0")
        for name in filter(None, tracked):
            if "__pycache__" in Path(name).parts or name.endswith(".pyc"):
                continue
            target = work / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(name, target)
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        commands = config.get("mutation_command") or " && ".join(
            shlex.join([sys.executable, *c]) for c in config["tests"]
        )
        test_command = shlex.join(["bash", "-c", "{ " + commands + "; } 2>&1"])
        cfg = report / "cosmic-ray.toml"
        cfg.write_text(
            f"[cosmic-ray]\nmodule-path = {json.dumps(sources)}\n"
            f"timeout = {float(mutant_timeout)}\nexcluded-modules = []\n"
            f"test-command = {json.dumps(test_command)}\n"
            '[cosmic-ray.distributor]\nname = "local"\n'
        )
        os.environ["IFRL_MUTATION_PHASE"] = "baseline"
        baseline = run(["bash", "-c", commands], report / "baseline.log", baseline_timeout, work)
        os.environ["IFRL_MUTATION_PHASE"] = "mutation"
        status["baseline_exit_code"] = baseline
        if baseline:
            status["status"] = "baseline-failed" if baseline != 124 else "incomplete"
            write_json(report / "status.json", status)
            return 1
        sample_db = cache / "session.sqlite"
        if sample_db.exists():
            with use_db(sample_db, WorkDB.Mode.open) as previous:
                finished = next(iter(previous.pending_work_items), None) is None
            if finished:
                # A completed campaign is rerun on the next daily invocation.
                # Only unfinished campaigns resume their saved pending work.
                shutil.copy2(sample_db, report / "previous-campaign.sqlite")
                sample_db.unlink()
        if not sample_db.exists():
            init = run(["cosmic-ray", "init", str(cfg), str(sample_db)],
                       report / "init.log", 300, work)
            status["init_exit_code"] = init
            if init:
                if sample_db.exists():
                    shutil.copy2(sample_db, report / "incomplete-init.sqlite")
                    sample_db.unlink()
                write_json(report / "status.json", status)
                return 1
        code = 0
        started = time.monotonic()
        with (
            use_db(sample_db, WorkDB.Mode.open) as database,
            chdir(work),
            (report / "execution.log").open("w") as log,
        ):
            for item in database.pending_work_items:
                if time.monotonic() - started > budget - mutant_timeout:
                    code = 124
                    break
                result = mutate_and_test(item.mutations, test_command, mutant_timeout)
                if "IFRL_MUTATION_INFRASTRUCTURE" in (result.output or ""):
                    result = evolve(result, test_outcome=TestOutcome.INCOMPETENT)
                database.set_result(item.job_id, result)
                print(item.job_id, result.worker_outcome, result.test_outcome,
                      file=log, flush=True)
        status["execution_exit_code"] = code
        with use_db(sample_db, WorkDB.Mode.open) as sample:
            results = list(sample.results)
            status["available_mutants"] = sample.num_work_items
            status["completed_mutants"] = len(results)
            status["outcomes"] = dict(Counter(
                "timeout" if result.output == "timeout"
                or "IFRL_MUTATION_TIMEOUT" in (result.output or "") else
                (result.test_outcome.value if result.test_outcome else result.worker_outcome.value)
                for _, result in results
            ))
            errors = any(
                result.worker_outcome.value != "normal"
                or (result.test_outcome is not None and result.test_outcome.value == "incompetent")
                for _, result in results
            )
        status["status"] = (
            "complete" if code == 0 and not errors
            and len(results) == status["available_mutants"] else "incomplete"
        )
        shutil.copy2(sample_db, report / "session.sqlite")
        write_json(report / "status.json", status)
        for command, filename in (
            (["cosmic-ray", "dump", str(sample_db)], "mutations.jsonl"),
            (["cr-report", str(sample_db), "--show-output", "--show-diff",
              "--show-pending"], "mutations.txt"),
            (["cr-html", str(sample_db)], "mutations.html"),
        ):
            if run(command, report / filename, 60, work):
                status["status"] = "report-failed"
        write_json(report / "status.json", status)
    print(json.dumps(status, indent=2))
    # Surviving mutants and individual mutation timeouts are reported as gaps.
    # Budget exhaustion is an explicit partial result, not a completed campaign.
    # Engine errors and failed baselines still fail the job.
    return int(errors or code not in (0, 124) or status["status"] == "report-failed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["lint", "coverage", "mutation"])
    args = parser.parse_args()
    config_path = Path(".ci/python.json")
    config = json.loads(config_path.read_text())
    report = Path("ci-reports") / args.mode
    report.mkdir(parents=True, exist_ok=True)
    report = report.resolve()
    write_json(report / "provenance.json", {
        "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "config": config, "python": sys.version,
        "run_url": f"{os.getenv('GITHUB_SERVER_URL', '')}/{os.getenv('GITHUB_REPOSITORY', '')}"
                   f"/actions/runs/{os.getenv('GITHUB_RUN_ID', '')}",
    })
    os.environ["PYTHONPATH"] = os.pathsep.join(
        part for part in config.get("pythonpath", ["."])
        + os.getenv("PYTHONPATH", "").split(os.pathsep) if part
    )
    if not config["sources"]:
        write_json(report / "status.json", {
            "status": "not-applicable", "reason": config["not_applicable"],
        })
        return 0
    if args.mode == "lint":
        code = run(["ruff", "check", "--isolated", *config["sources"]], report / "ruff.txt")
        print((report / "ruff.txt").read_text())
        return code
    if args.mode == "coverage":
        return coverage(config, report)
    return mutation(config, report)


if __name__ == "__main__":
    raise SystemExit(main())
