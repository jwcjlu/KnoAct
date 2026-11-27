KIND_RECOGNIZE, KIND_WRITE, KIND_PHRASE, KIND_WORD = "recognize", "write", "phrase", "word"
CN_KINDS = (KIND_RECOGNIZE, KIND_WRITE, KIND_PHRASE)
ALL_KINDS = CN_KINDS + (KIND_WORD,)
DEFAULT_CN_ENABLED = list(CN_KINDS)


def normalize_kind(k: str) -> str:
    k = (k or "").strip()
    if k not in ALL_KINDS:
        raise ValueError(f"invalid kind: {k}")
    return k


def default_kind_for_subject(subject: str) -> str:
    return KIND_PHRASE if (subject or "") == "语文" else KIND_WORD