import bcrypt


def hash_password(password: str) -> str:
    """Hashes a plain text password using bcrypt."""
    pw_bytes = password.encode('utf-8')
    if len(pw_bytes) > 72:
        raise ValueError("Password must be no more than 72 UTF-8 bytes.")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a stored bcrypt hash."""
    pw_bytes = plain_password.encode('utf-8')[:72]
    hash_bytes = hashed_password.encode('utf-8')
    try:
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception:
        return False
