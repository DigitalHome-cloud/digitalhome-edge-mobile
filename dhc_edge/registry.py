# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Atelier-5
# Copyright (C) 2026 DigitalHome.cloud
"""registry — every phone tested, kept on the PC: its check reports, its setup summaries, and one list of them all.

    reports/phones.json              one entry per model: what it is, what works, the last summary, your notes
    reports/phones.md                the same as a table, rewritten each time
    reports/<model>/<day>-check.json the phone check's whole report (check.html: Send report to the PC)
    reports/<model>/<day>-summary.txt the setup page's summary (step 6), and -summary.json its results

One file per model and day: a phone checked again the same day replaces that day's file, so tapping Send twice
keeps one. An entry's "notes" are yours: written by hand in phones.json, kept when the entry is updated.
Only what a phone says about itself is kept (model, browser, screen, what works): no pictures, no names.
Standard library only; the edge uses it (core.py), as atl-phone's bridge does.
"""
import json
import re
import time
from pathlib import Path

NEEDS = ("core", "nice", "later", "info")
DETAILS = {"android": "android", "chrome": "chrome", "screen": "screen", "webgl": "gpu", "camera": "camera",
           "front": "front camera", "faces": "faces", "vision": "vision", "network": "network", "headroom": "headroom"}


def slug(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", (model or "").strip())[:40].strip("._") or "unknown"


def day(at: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(at))


class Registry:
    def __init__(self, folder):
        self.dir = Path(folder)

    def _load(self) -> dict:
        try:
            data = json.loads((self.dir / "phones.json").read_text())
            if isinstance(data.get("phones"), dict):
                return data
        except (OSError, ValueError, AttributeError):
            pass
        return {"_": "Every phone tested with atl-phone (registry.py). Edit only the notes.", "phones": {}}

    def _entry(self, data: dict, model: str, at: float) -> dict:
        e = data["phones"].setdefault(model, {"model": model, "first": day(at), "notes": ""})
        e["last"] = day(at)
        return e

    def _save(self, data: dict):
        (self.dir / "phones.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        (self.dir / "phones.md").write_text(table(data))

    def check(self, report: dict, model: str, at: float = None) -> Path:
        """A phone check's report (check.html): kept whole, and summed up in the phone's entry."""
        at = at or time.time()
        model = slug(model)
        folder = self.dir / model
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{day(at)}-check.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        data = self._load()
        e = self._entry(data, model, at)
        checks = {k: v for k, v in report.get("checks", {}).items() if isinstance(v, dict)}
        e["ids"] = sorted(set(e.get("ids", [])) | ({report["phone_id"]} if report.get("phone_id") else set()))
        if report.get("userAgent"):
            e["user_agent"] = str(report["userAgent"])[:300]
        e["details"] = {name: str(checks[k].get("note", ""))[:120] for k, name in DETAILS.items() if k in checks}
        missing = {n: sorted(k for k, v in checks.items() if v.get("need") == n and v.get("ok") is False) for n in NEEDS[:3]}
        e["check"] = {"day": day(at), "file": str(path.relative_to(self.dir)),
                      "yes": sum(v.get("ok") is True for v in checks.values()),
                      "no": sum(v.get("ok") is False for v in checks.values()),
                      "tested": sum(bool(v.get("tested")) for v in checks.values()),
                      "verdict": "core missing: " + ", ".join(missing["core"]) if missing["core"] else "core complete",
                      "missing": missing}
        self._save(data)
        return path

    def summary(self, body: dict, model: str, at: float = None) -> Path:
        """The setup page's summary (step 6): its text, and what worked, test by test."""
        at = at or time.time()
        model = slug(model)
        folder = self.dir / model
        folder.mkdir(parents=True, exist_ok=True)
        text = str(body.get("text", ""))[:8000]
        results = {str(k)[:40]: v for k, v in (body.get("results") or {}).items() if v in (True, False, None, "na", "blocked")}
        path = folder / f"{day(at)}-summary.txt"
        path.write_text(text.rstrip() + "\n")
        (folder / f"{day(at)}-summary.json").write_text(json.dumps({"results": results, "robot": body.get("robot"),
                                                                    "contract": body.get("contract")}, indent=2) + "\n")
        data = self._load()
        e = self._entry(data, model, at)
        if body.get("id"):
            e["ids"] = sorted(set(e.get("ids", [])) | {str(body["id"])[:16]})
        e["summary"] = {"day": day(at), "file": str(path.relative_to(self.dir)),
                        "works": sorted(k for k, v in results.items() if v is True),
                        "fails": sorted(k for k, v in results.items() if v is False),
                        "untested": sorted(k for k, v in results.items() if v is None)}
        self._save(data)
        return path


def table(data: dict) -> str:
    rows = ["# Phones tested with atl-phone", "",
            "Written by `atl_phone/registry.py` from `phones.json` (edit the notes there). One folder per model with its reports.", "",
            "| Model | Android | Chrome | Screen | GPU | Check | Setup: fails / untested | Last | Notes |",
            "|---|---|---|---|---|---|---|---|---|"]
    for m, e in sorted(data["phones"].items()):
        d, ck, sm = e.get("details", {}), e.get("check", {}), e.get("summary", {})
        cell = lambda s: str(s).replace("|", "/").replace("\n", " ")
        setup = (", ".join(sm.get("fails", [])) or "none") + " / " + (", ".join(sm.get("untested", [])) or "none") if sm else "–"
        rows.append("| " + " | ".join(cell(v) for v in (m, d.get("android", ""), d.get("chrome", ""), d.get("screen", ""), d.get("gpu", ""),
                                                          ck.get("verdict", "–"), setup, e.get("last", ""), e.get("notes", ""))) + " |")
    return "\n".join(rows) + "\n"
