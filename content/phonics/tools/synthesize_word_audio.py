"""Synthesize example-word audio via project TTS into audio/word/."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.schema import load_rules  # noqa: E402

FFMPEG = Path(r"C:\Users\Admin\ffmpeg\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe")


def tts_synthesize(text: str) -> bytes:
    os.environ.setdefault(
        "DATABASE_URL",
        "sqlite:///D:/workspace/github/KnoAct/backend/zhixueban.db",
    )
    backend = Path(__file__).resolve().parents[3] / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from app.database import SessionLocal
    from app.services.tts import get_tts

    db = SessionLocal()
    try:
        return get_tts(db).synthesize(text, voice="", speed=0.95)
    finally:
        db.close()


def _to_wav(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".wav":
        if src != dest:
            dest.write_bytes(src.read_bytes())
        return
    cmd = [
        str(FFMPEG),
        "-y",
        "-i",
        str(src),
        "-acodec",
        "pcm_s16le",
        "-ar",
        "22050",
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def unique_words(rules_path: Path) -> list[str]:
    words: set[str] = set()
    for rule in load_rules(rules_path):
        for ex in rule.get("example_words") or []:
            w = (ex.get("word") or "").strip().lower()
            if w:
                words.add(w)
    return sorted(words)


def synthesize_words(
    root: Path,
    *,
    force: bool = False,
    limit: int | None = None,
) -> dict:
    root = Path(root)
    out_dir = root / "audio" / "word"
    out_dir.mkdir(parents=True, exist_ok=True)
    words = unique_words(root / "rules.yaml")
    if limit is not None:
        words = words[:limit]
    written = 0
    skipped = 0
    errors: list[str] = []
    for i, word in enumerate(words, 1):
        dest = out_dir / f"{word}.wav"
        if dest.is_file() and not force:
            skipped += 1
            continue
        try:
            payload = tts_synthesize(word)
            tmp = out_dir / f"{word}.tts.bin"
            tmp.write_bytes(payload)
            # sniff
            if payload.startswith(b"RIFF"):
                dest.write_bytes(payload)
                tmp.unlink(missing_ok=True)
            else:
                mp3 = out_dir / f"{word}.mp3"
                tmp.rename(mp3)
                _to_wav(mp3, dest)
                # keep mp3 optional; remove to save space
                mp3.unlink(missing_ok=True)
            written += 1
            if i % 20 == 0 or i == len(words):
                print(f"progress {i}/{len(words)} written={written}", flush=True)
        except Exception as e:  # noqa: BLE001 — batch continue
            errors.append(f"{word}: {e}")
            print(f"ERR {word}: {e}", flush=True)
    return {
        "total": len(words),
        "written": written,
        "skipped": skipped,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--force", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args(argv)
    result = synthesize_words(args.root, force=args.force, limit=args.limit)
    print(result)
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
