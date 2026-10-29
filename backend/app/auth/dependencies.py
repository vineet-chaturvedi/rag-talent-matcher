"""
Who is calling, and may they do this? (Step 9)

Authentication = WHO are you (a valid token for an active user).
Authorization  = WHAT may you do (your role allows this endpoint).

Endpoints declare what they need:
    user: User = Depends(get_current_user)   any logged-in, active user
    user: User = Depends(require_admin)      admins only
FastAPI runs these BEFORE the endpoint; if they raise, the endpoint never runs.

The token is read from the "Authorization: Bearer <token>" header (scripts, Swagger) or from the
HttpOnly cookie set at login (the browser / Next.js frontend). The user is loaded from the database on
every request, so deactivating someone or changing their role takes effect immediately, whatever their
token says.
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.auth.tokens import TokenError, decode_access_token
from app.config import get_settings
from app.db.enums import UserRole
from app.db.models import User

# tokenUrl makes Swagger's "Authorize" button work; auto_error=False lets us fall back to the cookie.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

_UNAUTHORIZED = {"WWW-Authenticate": "Bearer"}


async def get_current_user(
    request: Request,
    bearer: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    settings = get_settings()
    token = bearer or request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not logged in.", headers=_UNAUTHORIZED)
    try:
        claims = decode_access_token(token, settings.jwt_secret_value)
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc), headers=_UNAUTHORIZED)
    user = await db.get(User, int(claims["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This account is not active.", headers=_UNAUTHORIZED)
    request.state.user = user          # available to logging / auditing later in the request
    return user


def require_roles(*roles: UserRole):
    """Dependency factory: require_roles(UserRole.ADMIN) -> a dependency that allows only admins."""
    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"This action needs the role: {' or '.join(r.value for r in roles)}.")
        return user
    return checker


require_admin = require_roles(UserRole.ADMIN)
