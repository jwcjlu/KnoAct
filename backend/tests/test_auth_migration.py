from app.models import User
from app.seed import seed


def test_users_have_login_name_after_seed(setup_db, db):
    seed()
    user = db.query(User).order_by(User.id).first()
    assert user is not None
    assert user.login_name
