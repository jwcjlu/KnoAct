from datetime import datetime, timedelta

from conftest import make_user
from app.models import OtpCode
from app.services.otp import issue_otp, verify_otp


def test_issue_and_verify_otp(db):
    user = make_user(db, name="otp_user")
    db.commit()
    code = issue_otp(db, user.id, purpose="login")
    assert code == "123456"
    assert verify_otp(db, user.id, "login", code) is True
    assert verify_otp(db, user.id, "login", "000000") is False


def test_verify_expired_otp_fails(db):
    user = make_user(db, name="exp_user")
    db.commit()
    code = issue_otp(db, user.id, purpose="login")
    row = db.query(OtpCode).filter_by(user_id=user.id).one()
    row.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()
    assert verify_otp(db, user.id, "login", code) is False
