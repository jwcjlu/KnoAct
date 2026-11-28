"""Fix inaccurate / inconsistent rule audio (qu, tion, ture, awareness wav)."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.schema import load_rules  # noqa: E402

FFMPEG = Path(r"C:\Users\Admin\ffmpeg\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe")


def _read_pcm(path: Path) -> tuple[int, bytes]:
    with wave.open(str(path), "rb") as w:
        assert w.getsampwidth() == 2 and w.getnchannels() == 1
        return w.getframerate(), w.readframes(w.getnframes())


def _write_pcm(path: Path, rate: int, pcm: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


def _resample_pcm(pcm: bytes, src_rate: int, dst_rate: int) -> bytes:
    if src_rate == dst_rate:
        return pcm
    # Linear resample mono s16le via ffmpeg pipe for quality.
    cmd = [
        str(FFMPEG),
        "-y",
        "-f",
        "s16le",
        "-ar",
        str(src_rate),
        "-ac",
        "1",
        "-i",
        "pipe:0",
        "-f",
        "s16le",
        "-ar",
        str(dst_rate),
        "-ac",
        "1",
        "pipe:1",
    ]
    proc = subprocess.run(cmd, input=pcm, capture_output=True, check=True)
    return proc.stdout


def concat_wavs(parts: list[Path], dest: Path, *, gap_ms: int = 20) -> None:
    rates_pcms = [_read_pcm(p) for p in parts]
    rate = rates_pcms[0][0]
    chunks: list[bytes] = []
    gap = b"\x00\x00" * max(0, int(rate * gap_ms / 1000))
    for i, (r, pcm) in enumerate(rates_pcms):
        if r != rate:
            pcm = _resample_pcm(pcm, r, rate)
        if i:
            chunks.append(gap)
        chunks.append(pcm)
    _write_pcm(dest, rate, b"".join(chunks))


def _to_wav(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() == ".wav" and src.resolve() == dest.resolve():
        return
    if src.suffix.lower() == ".wav":
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
        "-ac",
        "1",
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


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
        return get_tts(db).synthesize(text, voice="", speed=0.85)
    finally:
        db.close()


def _tts_to_wav(text: str, dest: Path) -> None:
    payload = tts_synthesize(text)
    tmp = dest.with_suffix(".tmp.bin")
    tmp.write_bytes(payload)
    if payload.startswith(b"RIFF"):
        dest.write_bytes(payload)
        tmp.unlink(missing_ok=True)
        return
    _to_wav(tmp, dest)
    tmp.unlink(missing_ok=True)


def _patch_rule_audio(text: str, rid: str, rel: str, source: str) -> str:
    pat = re.compile(
        rf"(id:\s*{re.escape(rid)}\b.*?audio:\s*\n\s*rule:\s*\n"
        rf"\s*path:\s*)[^\n]+(\n\s*source:\s*)[^\n]+",
        re.DOTALL,
    )

    def _repl(m: re.Match[str]) -> str:
        return f"{m.group(1)}{rel}{m.group(2)}{source}"

    new, n = pat.subn(_repl, text, count=1)
    if n != 1:
        raise RuntimeError(f"failed to patch audio path for {rid}")
    return new


def repair(phonics_root: Path) -> dict:
    phonics_root = Path(phonics_root)
    rules_path = phonics_root / "rules.yaml"
    text = rules_path.read_text(encoding="utf-8")
    out_dir = phonics_root / "audio" / "rule"
    done: list[str] = []

    # 1) qu = /kw/ ← k + w (same pack, 24 kHz OLS)
    ols = phonics_root / "vendor" / "openlettersounds"
    qu_dest = out_dir / "consonant_digraph.qu.primary.wav"
    concat_wavs([ols / "k.wav", ols / "w.wav"], qu_dest, gap_ms=15)
    text = _patch_rule_audio(
        text, "consonant_digraph.qu.primary",
        "audio/rule/consonant_digraph.qu.primary.wav", "blend_ols",
    )
    done.append("consonant_digraph.qu.primary")

    # 2) tion = /ʃən/ ≈ sh + er (schwa-r colour) — closer than sh alone
    #    ture = /tʃə/ ≈ ch + er
    vox = phonics_root / "vendor" / "vocamax-ipa"
    tion_dest = out_dir / "syllable_pattern.tion.primary.wav"
    concat_wavs([vox / "sh.wav", vox / "er.wav"], tion_dest, gap_ms=10)
    text = _patch_rule_audio(
        text, "syllable_pattern.tion.primary",
        "audio/rule/syllable_pattern.tion.primary.wav", "blend_vocamax",
    )
    done.append("syllable_pattern.tion.primary")

    ture_dest = out_dir / "syllable_pattern.ture.primary.wav"
    concat_wavs([vox / "ch.wav", vox / "er.wav"], ture_dest, gap_ms=10)
    text = _patch_rule_audio(
        text, "syllable_pattern.ture.primary",
        "audio/rule/syllable_pattern.ture.primary.wav", "blend_vocamax",
    )
    done.append("syllable_pattern.ture.primary")

    # 3) r-controlled: TTS grapheme so r-colour is audible (ar/or/ore)
    for rid, prompt in (
        ("r_controlled.ar.primary", "ar. As in car. car."),
        ("r_controlled.or.primary", "or. As in for. for."),
        ("r_controlled.ore.primary", "ore. As in more. more."),
    ):
        dest = out_dir / f"{rid}.wav"
        _tts_to_wav(prompt, dest)
        text = _patch_rule_audio(text, rid, f"audio/rule/{rid}.wav", "tts")
        done.append(rid)

    # 4) awareness mp3 → wav
    for rid in (
        "syllable_pattern.closed_syllable.awareness",
        "syllable_pattern.open_syllable.awareness",
    ):
        mp3 = out_dir / f"{rid}.mp3"
        wav = out_dir / f"{rid}.wav"
        if mp3.is_file():
            _to_wav(mp3, wav)
            mp3.unlink()
        elif not wav.is_file():
            # re-TTS if neither exists
            rules = {r["id"]: r for r in load_rules(rules_path)}
            anchor = rules[rid]["example_words"][0]["word"]
            _tts_to_wav(f"{anchor}. {anchor}.", wav)
        text = _patch_rule_audio(text, rid, f"audio/rule/{rid}.wav", "tts")
        done.append(rid)

    rules_path.write_text(text, encoding="utf-8")
    load_rules(rules_path)
    return {"repaired": done, "count": len(done)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    args = p.parse_args(argv)
    print(repair(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
