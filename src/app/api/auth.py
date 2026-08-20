from datetime import timedelta

from flask import Blueprint, jsonify

from app.api import crud, security
from app.api.errors import HTTPExc
from app.api.models import UserCreate, UserDB, Token
from app.api.validation import validate_body, validate_login_form
from app.db import get_db
from app.config import get_settings

bp = Blueprint("auth", __name__)
settings = get_settings()


@bp.post("/register")
def register():
    """Register a new user"""
    payload = validate_body(UserCreate)
    session = get_db()

    # Check if username already exists
    user = crud.get_user_by_username(session, payload.username)
    if user:
        raise HTTPExc(400, "Username already registered")

    # Check if email already exists
    user = crud.get_user_by_email(session, payload.email)
    if user:
        raise HTTPExc(400, "Email already registered")

    hashed_password = security.get_password_hash(payload.password)
    crud.create_user(session, payload, hashed_password)

    # Return user data (without password)
    created = crud.get_user_by_username(session, payload.username)
    response = jsonify(UserDB(**created).model_dump(mode="json"))
    response.status_code = 201
    return response


@bp.post("/token")
def login_for_access_token():
    """Login to get access token"""
    username, password = validate_login_form()
    session = get_db()

    user = crud.get_user_by_username(session, username)
    if not user or not security.verify_password(password, user["hashed_password"]):
        raise HTTPExc(
            401,
            "Incorrect username or password",
            {"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = security.create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return jsonify(
        Token(access_token=access_token, token_type="bearer").model_dump(mode="json")
    )
