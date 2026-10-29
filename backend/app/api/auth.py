"""
Login and the current user (Step 9):
  POST /api/auth/login            email + password (JSON) -> token in the body AND an HttpOnly cookie
  POST /api/auth/token            the same, as an OAuth2 form: what Swagger's "Authorize" button uses
  POST /api/auth/logout           removes the cookie
  GET  /api/auth/me               who am I?
  POST /api/auth/change-password  change your own password
"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.auth import login_guard
from app.auth.dependencies import get_current_user
from app.auth.passwords import hash_password, password_problem, verify_password
from app.auth.tokens import create_access_token
from app.config import Settings, get_settings
from app.db.models import User
from app.schemas.auth import LoginRequest, PasswordChange, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _authenticate(db: AsyncSession, email: str, password: str) -> User:
    email = email.strip().lower()
    if wait := login_guard.seconds_locked(email):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Too many failed logins. Try again in {wait // 60 + 1} minutes.",
                            headers={"Retry-After": str(wait)})
    user = await db.scalar(select(User).where(func.lower(User.email) == email))
    # verify_password runs even when the user doesn't exist (same timing), and the message is the same
    # for "no such user" and "wrong password", so nobody can discover which emails have accounts.
    if not verify_password(password, user.hashed_password if user else None) or not user.is_active:
        login_guard.record_failure(email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password.",
                            headers={"WWW-Authenticate": "Bearer"})
    login_guard.record_success(email)
    return user


def _issue(user: User, response: Response, settings: Settings) -> TokenResponse:
    token, expires = create_access_token(user.id, user.role.value, settings.jwt_secret_value,
                                         settings.access_token_minutes)
    response.set_cookie(
        settings.auth_cookie_name, token,
        max_age=settings.access_token_minutes * 60,
        httponly=True,                          # JavaScript can't read it -> an XSS bug can't steal it
        secure=not settings.is_development,     # HTTPS only in production
        samesite="lax",                         # not sent on cross-site POSTs -> basic CSRF protection
        path="/",
    )
    return TokenResponse(access_token=token, expires_at=expires, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db),
                settings: Settings = Depends(get_settings)):
    return _issue(await _authenticate(db, body.email, body.password), response, settings)


@router.post("/token", response_model=TokenResponse, include_in_schema=False)
async def token_form(response: Response, form: OAuth2PasswordRequestForm = Depends(),
                     db: AsyncSession = Depends(get_db), settings: Settings = Depends(get_settings)):
    """Swagger's Authorize dialog calls this with 'username' (= email) and 'password'."""
    return _issue(await _authenticate(db, form.username, form.password), response, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, settings: Settings = Depends(get_settings)):
    response.delete_cookie(settings.auth_cookie_name, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(body: PasswordChange, user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The current password is wrong.")
    if problem := password_problem(body.new_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, problem)
    user.hashed_password = hash_password(body.new_password)
    await db.commit()
