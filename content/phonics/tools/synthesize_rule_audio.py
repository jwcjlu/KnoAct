"""Synthesize missing rule-level audio (TTS or --fake placeholders)."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.schema import load_rules  # noqa: E402


def minimal_wav_bytes(duration_ms: int = 50, sample_rate: int = 8000) -> bytes:
    """Minimal valid mono 16-bit PCM WAV (silent)."""
    num_samples = max(1, int(sample_rate * duration_ms / 1000))
    data_size = num_samples * 2
    byte_rate = sample_rate * 2
    block_align = 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        byte_rate,
        block_align,
        16,
        b"data",
        data_size,
    )
    return header + (b"\x00\x00" * num_samples)


def tts_synthesize(text: str) -> bytes:
    """Real TTS hook; override via env integration in a later phase."""
    raise RuntimeError(
        "TTS not configured; use --fake or wire tts_synthesize to your provider"
    )


def _rule_prompt(rule: dict) -> str:
    grapheme = rule.get("grapheme", "")
    ipa = rule.get("ipa", "")
    anchor = rule["example_words"][0]["word"]
    return f"{grapheme}. Sound {ipa}. As in {anchor}."


def synthesize_missing(root: Path, fake: bool = True) -> int:
    root = Path(root)
    rules = load_rules(root / "rules.yaml")
    written = 0
    for rule in rules:
        rule_audio = rule["audio"]["rule"]
        if rule_audio.get("source") != "tts":
            continue
        rel = rule_audio["path"]
        dest = root / rel
        if dest.is_file():
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        payload = minimal_wav_bytes() if fake else tts_synthesize(_rule_prompt(rule))
        dest.write_bytes(payload)
        written += 1
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synthesize missing rule audio files.")
    parser.add_argument("--root", type=Path, required=True, help="content/phonics root")
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Write minimal silent WAV instead of calling TTS",
    )
    args = parser.parse_args(argv)
    n = synthesize_missing(args.root, fake=args.fake)
    print(f"wrote {n} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())