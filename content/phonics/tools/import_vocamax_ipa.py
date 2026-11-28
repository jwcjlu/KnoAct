"""Map vocamax/ipa-audios phoneme WAVs onto remaining GPC rule audio (by IPA)."""

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

# rule_id -> vendor wav stem (under vendor/vocamax-ipa/)
RULE_TO_STEM: dict[str, str] = {
    "vowel.y.short": "ih",
    "consonant_digraph.sh.primary": "sh",
    "consonant_digraph.ch.primary": "ch",
    "consonant_digraph.th.primary": "th",
    "consonant_digraph.ck.primary": "k",
    "consonant_digraph.ng.primary": "ng",
    "consonant_digraph.wh.primary": "w",
    "consonant_digraph.ph.primary": "f",
    # qu /kw/ 由 repair_rule_audio 拼 k+w，勿用单字母 q
    "vowel_team.ai.primary": "ey",
    "vowel_team.ay.primary": "ey",
    "vowel_team.ee.primary": "iy",
    "vowel_team.ea.primary": "iy",
    "vowel_team.oa.primary": "ow",  # /oʊ/
    "vowel_team.ow.primary": "aw",  # our primary /aʊ/
    "vowel_team.oo.primary": "uw",
    "vowel_team.oi.primary": "oy",
    "vowel_team.oy.primary": "oy",
    "vowel_team.ou.primary": "aw",
    "vowel_team.aw.primary": "ao",
    "vowel_team.au.primary": "ao",
    "vowel_team.ew.primary": "uw",
    "vowel_team.ie.primary": "ay",
    "vowel_team.igh.primary": "ay",
    "vowel_team.ue.primary": "uw",
    "r_controlled.ar.primary": "aa",
    "r_controlled.or.primary": "ao",
    "r_controlled.er.primary": "er",
    "r_controlled.ir.primary": "er",
    "r_controlled.ur.primary": "er",
    "r_controlled.ore.primary": "ao",
    "syllable_pattern.a_e.magic_e": "ey",
    "syllable_pattern.e_e.magic_e": "iy",
    "syllable_pattern.i_e.magic_e": "ay",
    "syllable_pattern.o_e.magic_e": "ow",
    "syllable_pattern.u_e.magic_e": "uw",
    # tion/ture：完整弱读由 repair_rule_audio 拼 sh+er / ch+er，勿用单音素覆盖
    "syllable_pattern.le.primary": "l",  # approx /əl/
}


def _patch_rule_audio(text: str, rid: str, rel: str, source: str) -> tuple[str, int]:
    pat = re.compile(
        rf"(id:\s*{re.escape(rid)}\b.*?audio:\s*\n\s*rule:\s*\n"
        rf"\s*path:\s*)[^\n]+(\n\s*source:\s*)[^\n]+",
        re.DOTALL,
    )

    def _repl(m: re.Match[str]) -> str:
        return f"{m.group(1)}{rel}{m.group(2)}{source}"

    return pat.subn(_repl, text, count=1)


def import_pack(
    *,
    phonics_root: Path,
    vendor_dir: Path,
    ols_q: Path | None = None,
    dry_run: bool = False,
) -> dict:
    phonics_root = Path(phonics_root)
    vendor_dir = Path(vendor_dir)
    rules_path = phonics_root / "rules.yaml"
    text = rules_path.read_text(encoding="utf-8")
    patched: list[str] = []
    missing_vendor: list[str] = []

    mapping = dict(RULE_TO_STEM)
    # qu 不再从 OLS 的 q.wav 误拷；见 repair_rule_audio.concat k+w
    _ = ols_q  # CLI 兼容保留参数

    for rid, stem in mapping.items():
        src = vendor_dir / f"{stem}.wav"
        if not src.is_file():
            missing_vendor.append(f"{rid}->{stem}")
            continue
        rel = f"audio/rule/{rid}.wav"
        dest = phonics_root / rel
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            text, n = _patch_rule_audio(text, rid, rel, "vocamax_ipa")
            if n:
                patched.append(rid)
            else:
                missing_vendor.append(f"patch_failed:{rid}")

    if not dry_run:
        rules_path.write_text(text, encoding="utf-8")
        load_rules(rules_path)

    return {"patched": patched, "missing": missing_vendor, "count": len(patched)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--vendor", type=Path, default=ROOT / "vendor" / "vocamax-ipa")
    p.add_argument(
        "--ols-q",
        type=Path,
        default=ROOT / "vendor" / "openlettersounds" / "q.wav",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    print(
        import_pack(
            phonics_root=args.root,
            vendor_dir=args.vendor,
            ols_q=args.ols_q,
            dry_run=args.dry_run,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
