"""Generate letter_sounds_index.md (+ optional YAML) from rules.yaml."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from tools.letter_index import build_letter_index, render_letter_index_md  # noqa: E402
from tools.schema import load_rules  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rules", type=Path, default=ROOT / "rules.yaml")
    p.add_argument("--out-md", type=Path, default=ROOT / "letter_sounds_index.md")
    p.add_argument("--out-yaml", type=Path, default=ROOT / "letter_sounds_index.yaml")
    args = p.parse_args(argv)

    rules = load_rules(args.rules)
    by_id = {r["id"]: r for r in rules}
    index = build_letter_index(by_id)

    args.out_md.write_text(render_letter_index_md(index), encoding="utf-8")
    args.out_yaml.write_text(
        yaml.safe_dump({"letters": index}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"wrote {args.out_md} and {args.out_yaml}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
