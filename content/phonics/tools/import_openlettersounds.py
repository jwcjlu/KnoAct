"""Import Open Letter Sounds (CC0) into audio/rule and update rules.yaml sources."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.schema import load_rules  # noqa: E402

VOWEL_LETTERS = frozenset("aeiou")
CONSONANT_LETTERS = frozenset("bcdfghjklmnpqrstvwxz")


def letter_to_rule_id(letter: str) -> str | None:
    g = letter.lower()
    if g in VOWEL_LETTERS:
        return f"vowel.{g}.short"
    if g in CONSONANT_LETTERS:
        return f"consonant.{g}.primary"
    return None


def import_pack(*, phonics_root: Path, vendor_dir: Path, dry_run: bool = False) -> dict:
    phonics_root = Path(phonics_root)
    vendor_dir = Path(vendor_dir)
    rules_path = phonics_root / "rules.yaml"
    text = rules_path.read_text(encoding="utf-8")

    copied = 0
    patched_ids: list[str] = []
    skipped: list[str] = []

    for wav in sorted(vendor_dir.glob("*.wav")):
        letter = wav.stem.lower()
        rid = letter_to_rule_id(letter)
        if rid is None:
            skipped.append(letter)
            continue
        rel = f"audio/rule/{rid}.wav"
        dest = phonics_root / rel
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(wav, dest)
        # Patch only this rule's audio.rule line (flow or block style).
        pat = re.compile(
            rf"(id:\s*{re.escape(rid)}\b.*?audio:\s*\n\s*rule:\s*\{{path:\s*)"
            rf"[^,\}}]+(,\s*source:\s*)[^\}}]+(\}})",
            re.DOTALL,
        )

        def _repl(m: re.Match[str]) -> str:
            return f"{m.group(1)}{rel}{m.group(2)}openlettersounds{m.group(3)}"

        new_text, n = pat.subn(_repl, text, count=1)
        if n == 0:
            # Try multiline block form
            pat2 = re.compile(
                rf"(id:\s*{re.escape(rid)}\b.*?audio:\s*\n\s*rule:\s*\n"
                rf"\s*path:\s*)[^\n]+(\n\s*source:\s*)[^\n]+",
                re.DOTALL,
            )

            def _repl2(m: re.Match[str]) -> str:
                return f"{m.group(1)}{rel}{m.group(2)}openlettersounds"

            new_text, n = pat2.subn(_repl2, text, count=1)
        if n:
            text = new_text
            patched_ids.append(rid)
        copied += 1

    if not dry_run:
        rules_path.write_text(text, encoding="utf-8")
        load_rules(rules_path)

    return {
        "copied": copied,
        "patched": len(patched_ids),
        "patched_ids": patched_ids,
        "skipped_letters": skipped,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--vendor", type=Path, default=ROOT / "vendor" / "openlettersounds")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    print(import_pack(phonics_root=args.root, vendor_dir=args.vendor, dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
