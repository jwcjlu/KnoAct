"""OTP issue/verify; stores hashed codes only."""

import hashlib
import os
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import OtpCode, User
from app.services.sms import send_otp_sms

OTP_TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5
FAKE_CODE = "123456"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _use_fixed_code() -> bool:
    if os.environ.get("SMS_FAKE_CODE") == "1":
        return True
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    return False


def _generate_code() -> str:
    if _use_fixed_code():
        return FAKE_CODE
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_otp(
    db: Session,
    user_id: int,
    purpose: str,
    channel: str = "phone",
) -> str:
    """Store hashed OTP; return plaintext (for fake SMS in dev/test)."""
    code = _generate_code()
    row = OtpCode(
        user_id=user_id,
        channel=channel,
        purpose=purpose,
        code_hash=_hash_code(code),
        expires_at=datetime.utcnow() + OTP_TTL,
        attempts=0,
    )
    db.add(row)
    db.commit()

    user = db.get(User, user_id)
    if channel == "phone" and user and user.phone:
        send_otp_sms(user.phone, code)
    return code


def verify_otp(db: Session, user_id: int, purpose: str, code: str) -> bool:
    """Verify latest non-expired OTP for user+purpose; increments attempts on mismatch."""
    now = datetime.utcnow()
    row = (
        db.query(OtpCode)
        .filter(
            OtpCode.user_id == user_id,
            OtpCode.purpose == purpose,
            OtpCode.expires_at >= now,
        )
        .order_by(OtpCode.id.desc())
        .first()
    )
    if not row:
        return False
    if row.attempts >= MAX_ATTEMPTS:
        return False
    if _hash_code(code) != row.code_hash:
        row.attempts += 1
        db.commit()
        return False
    return True
