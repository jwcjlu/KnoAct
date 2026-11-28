"""Build audio_manifest.yaml from rules.yaml and the audio/ tree."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.schema import load_rules  # noqa: E402


def _resolve_exists(phonics_root: Path, expected_path: str) -> bool:
    return (phonics_root / expected_path).is_file()


def build_manifest(rules_path, audio_root) -> dict:
    rules_path = Path(rules_path)
    phonics_root = rules_path.parent
    _ = Path(audio_root)  # anchors content/phonics/audio for CLI symmetry

    manifest_rules: list[dict] = []
    for rule in load_rules(rules_path):
        rule_audio = rule["audio"]["rule"]
        expected_path = rule_audio["path"]
        row: dict = {
            "id": rule["id"],
            "expected_path": expected_path,
            "exists": _resolve_exists(phonics_root, expected_path),
            "source": rule_audio["source"],
            "examples": [],
        }

        by_word: dict[str, dict] = {}
        for entry in rule["audio"].get("examples") or []:
            w = (entry.get("word") or "").lower()
            if w:
                by_word[w] = entry

        for ex in rule.get("example_words") or []:
            word = ex["word"]
            key = word.lower()
            if key in by_word:
                override = by_word[key]
                ex_path = override.get("path") or f"audio/word/{key}.wav"
                ex_source = override.get("source", "tts")
            else:
                ex_path = f"audio/word/{key}.wav"
                ex_source = "tts"
            row["examples"].append({
                "word": word,
                "expected_path": ex_path,
                "exists": _resolve_exists(phonics_root, ex_path),
                "source": ex_source,
            })

        manifest_rules.append(row)

    return {"rules": manifest_rules}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate phonics audio manifest YAML.")
    parser.add_argument("--rules", type=Path, required=True, help="Path to rules.yaml")
    parser.add_argument(
        "--audio-root",
        type=Path,
        required=True,
        help="Path to audio/ directory under content/phonics",
    )
    parser.add_argument("--out", type=Path, required=True, help="Output audio_manifest.yaml path")
    args = parser.parse_args(argv)

    import yaml

    data = build_manifest(args.rules, args.audio_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())