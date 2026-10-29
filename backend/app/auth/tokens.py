"""
Access tokens (Step 9): signed JSON Web Tokens (JWT).

After a successful login the server issues a token like  xxxxx.yyyyy.zzzzz  =  header.payload.signature
  header    {"alg": "HS256", "typ": "JWT"}
  payload   {"sub": "3", "role": "admin", "iat": 1793..., "exp": 1793...}     (readable by anyone! no secrets in it)
  signature HMAC-SHA256(header + payload, JWT_SECRET)                          (only the server can make it)

Every request sends the token back. The server recomputes the signature: if anyone changed the payload
(e.g. "role": "admin"), the signature no longer matches and the token is rejected. No session table needed.
The expiry ("exp") limits the damage if a token is stolen.
"""
from datetime import datetime, timedelta, timezone

import jwt

ALGORITHM = "HS256"


class TokenError(Exception):
    """Invalid, tampered or expired token."""


def create_access_token(user_id: int, role: str, secret: str, minutes: int) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=minutes)
    payload = {"sub": str(user_id), "role": role, "iat": now, "exp": expires, "typ": "access"}
    return jwt.encode(payload, secret, algorithm=ALGORITHM), expires


def decode_access_token(token: str, secret: str) -> dict:
    try:
        # algorithms=[...] is essential: never let the token choose its own algorithm ("alg": "none" attack).
        claims = jwt.decode(token, secret, algorithms=[ALGORITHM], options={"require": ["sub", "exp", "iat"]})
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Your session has expired; please log in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Invalid token.") from exc
    if claims.get("typ") != "access":
        raise TokenError("Invalid token type.")
    return claims
