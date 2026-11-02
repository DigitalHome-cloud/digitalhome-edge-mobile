#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atelier-5
# Copyright (C) 2026 DigitalHome.cloud
"""build.py — renders the diagrams in src/ with Archify and keeps each run's evidence in receipts/.

Copy it to <repo>/docs/architecture/ (from the atl-architecture-docs skill); it takes the repository as two levels up.

    python3 build.py            # every diagram
    python3 build.py 03- 05-    # only those whose name starts so

Needs Node.js 18+ and the Archify skill (~/.agents/skills/archify or ~/.claude/skills/archify).
Every diagram cites source lines at the commit in its meta.repository; Archify checks them against
that commit's bytes, and it needs the repository's origin to match meta.repository.url. While this
repository has no origin (not pushed yet), the check runs on a throwaway clone that carries the
intended origin, so this repository's own configuration is left alone.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent


def archify() -> Path:
    for base in (Path.home() / ".agents/skills/archify", Path.home() / ".claude/skills/archify"):
        if (base / "bin/archify.mjs").is_file():
            return base / "bin/archify.mjs"
    sys.exit("Archify is missing: install the skill under ~/.agents/skills or ~/.claude/skills")


def git(*args, cwd=REPO) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout.strip()


def evidence_root(repository: dict, tmp: Path) -> Path:
    """The repository to check citations against: this one if its origin matches, else a clone that does."""
    if git("remote", "get-url", "origin") == repository["url"]:
        return REPO
    clone = tmp / "repo"
    subprocess.run(["git", "clone", "-q", str(REPO), str(clone)], check=True)
    subprocess.run(["git", "remote", "set-url", "origin", repository["url"]], cwd=clone, check=True)
    if subprocess.run(["git", "cat-file", "-e", repository["revision"] + "^{commit}"], cwd=clone).returncode:
        sys.exit(f"commit {repository['revision'][:7]} is not in this repository: commit first, or update meta.repository")
    return clone


def main() -> int:
    prefixes = sys.argv[1:]
    sources = sorted(p for p in (HERE / "src").glob("*.json") if not prefixes or p.name.startswith(tuple(prefixes)))
    if not sources:
        sys.exit("nothing to build")
    tool = archify()
    results = {}
    with tempfile.TemporaryDirectory(prefix="atl-phone-archify-") as tmp:
        root = None
        for src in sources:
            spec = json.loads(src.read_text())
            kind, out = src.name.split(".")[-2], spec["meta"]["output"]
            root = root or evidence_root(spec["meta"]["repository"], Path(tmp))
            receipts = HERE / "receipts" / src.name.split(".")[0]
            shutil.rmtree(receipts, ignore_errors=True)  # a new run, its own evidence
            run = subprocess.run(["node", str(tool), "finalize", kind, str(src.relative_to(HERE)), out,
                                  "--repo-root", str(root), "--quality", spec["meta"].get("quality_profile", "showcase"),
                                  "--out-dir", str(receipts.relative_to(HERE)), "--json"],
                                 cwd=HERE, capture_output=True, text=True)
            try:
                receipt = json.loads(run.stdout)
            except ValueError:
                receipt = {"status": "error", "gates": {}, "diagnostics": [{"code": "no-receipt", "message": run.stderr[-400:]}]}
            results[src.name] = {"output": out, "status": receipt.get("status"), "gates": receipt.get("gates"),
                                 "diagnostics": [d.get("code") for d in receipt.get("diagnostics", [])]}
            print(f"{'PASS' if run.returncode == 0 else 'FAIL'}  {src.name} -> {out}")
            for d in receipt.get("diagnostics", []):
                print(f"      {d.get('code')}: {d.get('message', '')[:200]}")
    summary = HERE / "receipts" / "summary.json"
    old = json.loads(summary.read_text()) if summary.is_file() else {}
    summary.write_text(json.dumps({"revision": spec["meta"]["repository"]["revision"],
                                   "diagrams": {**old.get("diagrams", {}), **results}}, indent=2) + "\n")
    failed = [k for k, v in results.items() if v["status"] != "pass"]
    print("all passed" if not failed else f"{len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
