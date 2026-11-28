"""Synthesize missing rule-level audio (TTS or --fake placeholders)."""

from __future__ import annotations

import argparse
import os
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
    """Call project TTS (get_tts) using DATABASE_URL / backend on PYTHONPATH."""
    backend = Path(__file__).resolve().parents[3] / "backend"
    # Prefer main-repo DB when worktree DB is empty
    os.environ.setdefault(
        "DATABASE_URL",
        "sqlite:///D:/workspace/github/KnoAct/backend/zhixueban.db",
    )
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from app.database import SessionLocal
    from app.services.tts import get_tts

    db = SessionLocal()
    try:
        tts = get_tts(db)
        return tts.synthesize(text, voice="", speed=0.9)
    finally:
        db.close()


def _rule_prompt(rule: dict) -> str:
    grapheme = rule.get("grapheme", "")
    ipa = (rule.get("ipa") or "").strip()
    anchor = rule["example_words"][0]["word"]
    if grapheme in ("closed_syllable", "open_syllable"):
        # Awareness: speak the anchor word clearly twice
        return f"{anchor}. {anchor}."
    if ipa:
        return f"{grapheme}. As in {anchor}. {anchor}."
    return f"{grapheme}. {anchor}."


def _audio_ext(payload: bytes) -> str:
    if payload.startswith(b"RIFF"):
        return ".wav"
    if payload[:3] == b"ID3" or payload[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return ".mp3"
    return ".bin"


def synthesize_missing(
    root: Path,
    *,
    fake: bool = True,
    force: bool = False,
    only_ids: set[str] | None = None,
) -> int:
    root = Path(root)
    rules = load_rules(root / "rules.yaml")
    written = 0
    for rule in rules:
        if only_ids is not None and rule["id"] not in only_ids:
            continue
        rule_audio = rule["audio"]["rule"]
        if rule_audio.get("source") != "tts":
            continue
        rel = rule_audio["path"]
        dest = root / rel
        if dest.is_file() and not force:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if fake:
            payload = minimal_wav_bytes()
            out = dest
        else:
            payload = tts_synthesize(_rule_prompt(rule))
            ext = _audio_ext(payload)
            out = dest.with_suffix(ext) if dest.suffix != ext else dest
            if out != dest:
                # Keep rules path if wav requested but got mp3 — write as .mp3 and leave
                # path update to caller; for simplicity write bytes to dest path anyway
                # when formats differ players may still sniff. Prefer correct suffix file.
                out.write_bytes(payload)
                if dest.exists() and dest != out:
                    try:
                        dest.unlink()
                    except OSError:
                        pass
                written += 1
                continue
        out.write_bytes(payload)
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files for source=tts rules",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="Only synthesize these rule ids (repeatable)",
    )
    args = parser.parse_args(argv)
    only = set(args.only) if args.only else None
    n = synthesize_missing(
        args.root, fake=args.fake, force=args.force, only_ids=only
    )
    print(f"wrote {n} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
