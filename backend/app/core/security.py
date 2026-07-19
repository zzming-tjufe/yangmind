import hashlib
import hmac
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import settings


def hash_password(plain: str) -> str:
    """把明文密码变成不可逆的哈希，再存进数据库。"""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """登录时：用用户输入的密码，和库里的哈希比对。"""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _password_token_version(password_hash: str) -> str:
    """Bind a token to the current password without storing extra session state."""
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        password_hash.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def create_access_token(user_id: int, password_hash: str) -> str:
    """登录成功后发一张「门禁卡」(JWT)。"""
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "ver": _password_token_version(password_hash),
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> tuple[int, str] | None:
    """验卡：解析出用户 id；无效或过期则返回 None。"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        sub = payload.get("sub")
        version = payload.get("ver")
        if sub is None or not isinstance(version, str):
            return None
        return int(sub), version
    except (InvalidTokenError, TypeError, ValueError):
        return None


def access_token_matches_password(token_version: str, password_hash: str) -> bool:
    return hmac.compare_digest(token_version, _password_token_version(password_hash))
