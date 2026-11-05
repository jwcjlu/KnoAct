import os, time, jwt
from passlib.context import CryptContext

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET = os.environ.get("JWT_SECRET", "dev-change-me")
ACCESS_TTL = int(os.environ.get("JWT_ACCESS_TTL", "3600"))


def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def create_access_token(claims: dict, ttl: int = ACCESS_TTL) -> str:
    payload = {**claims, "exp": int(time.time()) + ttl}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        SECRET,
        algorithms=["HS256"],
        options={"verify_sub": False},
    )
