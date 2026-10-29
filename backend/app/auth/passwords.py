"""
Password hashing (Step 9).

We never store a password, only a HASH: a one-way fingerprint. At login we hash what the person typed
and compare. If the database leaks, the attacker gets hashes, not passwords.

Argon2id (via pwdlib) is the current recommendation (OWASP, and FastAPI's own docs). It is deliberately
SLOW and MEMORY-HUNGRY (~50-100 ms and 64 MB per hash), so guessing billions of passwords on GPUs is
impractical. Each hash also contains a random SALT, so two people with the same password get different hashes:
    $argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>
"""
from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()        # Argon2id with sensible defaults

MIN_PASSWORD_LENGTH = 12

# Used when the email doesn't exist, so a failed login takes the same time either way.
# Otherwise an attacker could tell "no such user" (fast) from "wrong password" (slow).
_DUMMY_HASH = _hasher.hash("not-a-real-password-just-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if hashed is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return _hasher.verify(password, hashed)


def password_problem(password: str) -> str | None:
    """A simple, honest policy: long beats complicated (NIST SP 800-63B). Returns a message or None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if password.strip() != password:
        return "Password must not start or end with spaces."
    return None
