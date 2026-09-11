from functools import wraps

from flask import g, request
from jose import JWTError, jwt

from app.api import crud
from app.api.errors import HTTPExc
from app.api.models import TokenData, UserDB
from app.db import get_db
from app.config import get_settings

settings = get_settings()

# The FastAPI app declared OAuth2PasswordBearer(tokenUrl="auth/token"); the
# bearer-token extraction it performed implicitly is done explicitly here.
TOKEN_URL = "auth/token"


def _unauthorized(detail: str) -> HTTPExc:
    return HTTPExc(401, detail, {"WWW-Authenticate": "Bearer"})


def _bearer_token() -> str:
    """Replicates OAuth2PasswordBearer: missing/!bearer -> 'Not authenticated'."""
    header = request.headers.get("Authorization")
    if not header:
        raise _unauthorized("Not authenticated")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("Not authenticated")
    return token


def get_current_user() -> UserDB:
    token = _bearer_token()
    credentials_exception = _unauthorized("Could not validate credentials")
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    user = crud.get_user_by_username(get_db(), username=token_data.username)
    if user is None:
        raise credentials_exception

    return UserDB(**user)


def get_current_active_user() -> UserDB:
    current_user = get_current_user()
    if not current_user.is_active:
        raise HTTPExc(400, "Inactive user")
    return current_user


def auth_required(view):
    """Route decorator replacing ``Depends(get_current_active_user)``.

    FastAPI resolves security dependencies before validating body/path/query
    parameters, so authentication must run before any 422 can be raised. This
    decorator wraps the view so that ordering is preserved.
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        g.current_user = get_current_active_user()
        return view(*args, **kwargs)

    return wrapper


def current_user() -> UserDB:
    return g.current_user
