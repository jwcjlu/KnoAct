from app.services.security import hash_password, verify_password, create_access_token, decode_access_token


def test_password_hash_roundtrip():
    h = hash_password("abc12345")
    assert verify_password("abc12345", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token({"sub": 42})
    payload = decode_access_token(token)
    assert payload["sub"] == 42
