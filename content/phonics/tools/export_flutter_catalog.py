"""Export phonics catalog.json + sync audio into student-app/assets/phonics/."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.schema import load_rules  # noqa: E402


def _load_path(path_yaml: Path) -> list[dict]:
    import yaml

    data = yaml.safe_load(path_yaml.read_text(encoding="utf-8"))
    return list(data.get("stages") or [])


def build_catalog(phonics_root: Path) -> dict:
    rules = load_rules(phonics_root / "rules.yaml")
    stages = _load_path(phonics_root / "path.yaml")
    out_rules = []
    for r in rules:
        rule_audio = (r.get("audio") or {}).get("rule") or {}
        words = []
        for ex in r.get("example_words") or []:
            w = (ex.get("word") or "").strip()
            if not w:
                continue
            words.append(
                {
                    "word": w,
                    "grades": list(ex.get("grades") or [3, 5]),
                    "audio": f"phonics/audio/word/{w.lower()}.wav",
                }
            )
        rel = rule_audio.get("path") or f"audio/rule/{r['id']}.wav"
        # strip content-relative "audio/" → asset-relative under phonics/
        asset_rule = "phonics/" + rel.lstrip("/")
        out_rules.append(
            {
                "id": r["id"],
                "category": r["category"],
                "grapheme": r["grapheme"],
                "ipa": r.get("ipa") or "",
                "approx_zh": r.get("approx_zh") or "",
                "path_order": r.get("path_order"),
                "notes": r.get("notes") or "",
                "rule_audio": asset_rule,
                "example_words": words,
            }
        )
    return {"version": 1, "stages": stages, "rules": out_rules}


def sync_audio(phonics_root: Path, assets_root: Path) -> dict:
    counts = {"rule": 0, "word": 0}
    for kind in ("rule", "word"):
        src = phonics_root / "audio" / kind
        dest = assets_root / "audio" / kind
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        if not src.is_dir():
            continue
        for f in src.iterdir():
            if f.suffix.lower() in (".wav", ".mp3") and f.is_file():
                shutil.copy2(f, dest / f.name)
                counts[kind] += 1
    return counts


def export(*, phonics_root: Path, student_app: Path) -> dict:
    phonics_root = Path(phonics_root)
    assets = Path(student_app) / "assets" / "phonics"
    assets.mkdir(parents=True, exist_ok=True)
    catalog = build_catalog(phonics_root)
    catalog_path = assets / "catalog.json"
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    counts = sync_audio(phonics_root, assets)
    return {
        "catalog": str(catalog_path),
        "rules": len(catalog["rules"]),
        "stages": len(catalog["stages"]),
        **counts,
    }


def main(argv: list[str] | None = None) -> int:
    repo = ROOT.parents[1]  # worktree or repo root containing content/ + student-app/
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument(
        "--student-app",
        type=Path,
        default=repo / "student-app",
    )
    args = p.parse_args(argv)
    print(export(phonics_root=args.root, student_app=args.student_app))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
