"""以学生 jinyuxuan 身份把当天全部任务做一遍，打印每步结果，供找 bug。"""
from __future__ import annotations

import base64
import io
import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

# 保证可 import app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.security import create_access_token

API = "http://127.0.0.1:8010"
UID = 11
TODAY = date.today().isoformat()


def _tiny_png() -> bytes:
    # 1x1 PNG
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )


def req(method: str, path: str, token: str, body=None, multipart: dict | None = None):
    url = API + path
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if multipart is not None:
        boundary = "----KnoActBoundary7MA4YWxkTrZu0gW"
        parts = []
        for k, v in multipart.items():
            if isinstance(v, tuple):
                filename, raw, ctype = v
                parts.append(
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{k}"; filename="{filename}"\r\n'
                    f"Content-Type: {ctype}\r\n\r\n".encode()
                    + raw
                    + b"\r\n"
                )
            else:
                parts.append(
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{k}"\r\n\r\n'
                    f"{v}\r\n".encode()
                )
        parts.append(f"--{boundary}--\r\n".encode())
        data = b"".join(parts)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"raw": raw}
        return e.code, parsed


def main():
    token = create_access_token({"sub": str(UID), "role": "child"})
    failures = []

    def check(step: str, ok: bool, detail):
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {step}: {json.dumps(detail, ensure_ascii=False)[:400]}")
        if not ok:
            failures.append((step, detail))

    # 1) list tasks
    code, tasks = req("GET", f"/api/tasks?user_id={UID}&date={TODAY}&role=child", token)
    check("list_tasks", code == 200 and isinstance(tasks, list) and len(tasks) >= 1, {"code": code, "n": len(tasks) if isinstance(tasks, list) else tasks})
    if code != 200:
        return 1
    by_type = {(t["task_type"], t["subject"]): t for t in tasks}
    print("tasks:", [(t["id"], t["subject"], t["task_type"], t["submit_status"]) for t in tasks])

    # ---- dictation helper ----
    def do_dictation(t):
        tid = t["id"]
        words = json.loads(t["content"] or "[]")
        # 上传听写照
        code, up = req(
            "POST",
            f"/api/tasks/{tid}/upload-photo",
            token,
            multipart={"file": ("dictation.png", _tiny_png(), "image/png")},
        )
        check(f"dictation[{tid}].upload", code == 200 and up.get("ok") is True, {"code": code, "body": up})
        # 逐词 grade（可选）
        for w in words:
            code, g = req(
                "POST",
                "/api/dictation/grade",
                token,
                {"user_id": UID, "word_id": w.get("id"), "word": w["word"], "answer": w["word"]},
            )
            check(f"dictation[{tid}].grade:{w['word']}", code == 200 and g.get("correct") is True, {"code": code, "body": g})
        code, done = req(
            "POST",
            "/api/dictation/complete",
            token,
            {"user_id": UID, "correct": len(words), "wrong": 0, "wrong_words": []},
        )
        check(f"dictation[{tid}].complete", code == 200 and "points_awarded" in done, {"code": code, "body": done})
        code, sub = req("POST", f"/api/tasks/{tid}/submit", token)
        check(f"dictation[{tid}].submit", code == 200 and sub.get("ok") is True, {"code": code, "body": sub})

    # ---- knowledge helper ----
    def do_knowledge(t):
        tid = t["id"]
        points = json.loads(t["content"] or "[]")
        answers = [
            {"id": p["id"], "user_answer": p.get("answer") or "", "duration_ms": 1000}
            for p in points
        ]
        code, g = req(
            "POST",
            f"/api/tasks/{tid}/knowledge-review",
            token,
            {"user_id": UID, "answers": answers},
        )
        check(
            f"knowledge[{tid}].grade",
            code == 200 and g.get("ok") is True,
            {"code": code, "body": g},
        )
        # knowledge grade already sets submit_status=submitted; extra submit may be noop/ok
        code, sub = req("POST", f"/api/tasks/{tid}/submit", token)
        check(
            f"knowledge[{tid}].submit",
            code == 200 and (sub.get("ok") is True or "error" in (sub or {})),
            {"code": code, "body": sub},
        )

    # ---- listening ----
    def do_listening(t):
        tid = t["id"]
        code, mat = req("GET", f"/api/listening/material?user_id={UID}", token)
        check(f"listening[{tid}].material", code == 200 and "questions" in mat, {"code": code, "keys": list(mat) if isinstance(mat, dict) else mat})
        qs = (mat or {}).get("questions") or []
        # 听力只靠错题本 + 任务提交；前端本地判分后 submit
        # 确保 content 有题
        if not qs:
            failures.append((f"listening[{tid}].empty", mat))
        code, sub = req("POST", f"/api/tasks/{tid}/submit", token)
        check(f"listening[{tid}].submit", code == 200 and sub.get("ok") is True, {"code": code, "body": sub})

    # ---- math ----
    def do_math(t):
        tid = t["id"]
        code, mat = req("GET", f"/api/math/task/{tid}/material", token)
        check(f"math[{tid}].material", code == 200 and mat.get("ok") is True, {"code": code, "body": {k: mat.get(k) for k in ('ok','title','calc','word') if isinstance(mat, dict)}})
        # 取标准答案：从 DB content（material 不下发 answer）
        from app.database import SessionLocal
        from app.models import Task
        from app.services.math_gen import parse_math_task_content
        db = SessionLocal()
        task = db.get(Task, tid)
        parsed = parse_math_task_content(task.content or "")
        db.close()
        answers = [str(c.get("answer") or "") for c in parsed["calc"]]
        code, g = req(
            "POST",
            f"/api/math/task/{tid}/grade",
            token,
            {"user_id": UID, "answers": answers},
        )
        check(f"math[{tid}].grade", code == 200 and g.get("ok") is True, {"code": code, "body": g})
        # 应用题拍照
        for w in parsed.get("word") or []:
            idx = w.get("index")
            # material word items use enumerate index; upload uses word_index
        for i, _w in enumerate(parsed.get("word") or []):
            code, up = req(
                "POST",
                f"/api/tasks/{tid}/upload-photo",
                token,
                multipart={
                    "file": ("math_word.png", _tiny_png(), "image/png"),
                    "word_index": str(i),
                },
            )
            check(f"math[{tid}].word_photo[{i}]", code == 200 and up.get("ok") is True, {"code": code, "body": up})
        code, sub = req("POST", f"/api/tasks/{tid}/submit", token)
        check(f"math[{tid}].submit", code == 200 and sub.get("ok") is True, {"code": code, "body": sub})

    # 按科目顺序跑
    order = [
        ("dictation", "语文"),
        ("knowledge", "语文"),
        ("dictation", "英语"),
        ("knowledge", "英语"),
        ("listening", "英语"),
        ("knowledge", "数学"),
        ("math", "数学"),
    ]
    for tt, subj in order:
        t = by_type.get((tt, subj))
        if not t:
            check(f"missing:{tt}:{subj}", False, "task not found")
            continue
        if tt == "dictation":
            do_dictation(t)
        elif tt == "knowledge":
            do_knowledge(t)
        elif tt == "listening":
            do_listening(t)
        elif tt == "math":
            do_math(t)

    # 复查
    code, tasks2 = req("GET", f"/api/tasks?user_id={UID}&date={TODAY}&role=child", token)
    print("\n=== final statuses ===")
    for t in tasks2 if isinstance(tasks2, list) else []:
        print(t["id"], t["subject"], t["task_type"], t["submit_status"], "photo=", bool(t.get("photo_path")))

    # 做题明细
    parent_token = create_access_token({"sub": "12", "role": "parent"})
    code, ar = req("GET", f"/api/answer-records?user_id={UID}&target_date={TODAY}", parent_token)
    check("answer_records", code == 200 and ar.get("total", 0) > 0, {"code": code, "total": ar.get("total"), "modules": [r.get("module") for r in ar.get("records", [])]})

    print("\n=== FAILURES ===")
    for s, d in failures:
        print("-", s, "=>", d)
    print(f"total failures: {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
