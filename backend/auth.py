from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from backend.database import get_conn

SECRET_KEY = "swap-robot-care-secret-2026"
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def create_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": str(user_id), "username": username, "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return {}


def register_user(username: str, password: str) -> dict:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, hashed_pw) VALUES (?, ?)",
            (username, hash_password(password)),
        )
        conn.commit()
        row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        return {"ok": True, "user_id": row["id"], "username": username}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def login_user(username: str, password: str) -> dict:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if not row or not verify_password(password, row["hashed_pw"]):
        return {"ok": False, "error": "用户名或密码错误"}
    return {"ok": True, "user_id": row["id"], "username": row["username"]}
