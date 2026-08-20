from flask import Blueprint, jsonify
from pydantic import BaseModel
from sqlalchemy import text

from app.db import get_db

bp = Blueprint("ping", __name__)


class PingResponse(BaseModel):
    """Ping response schema"""

    status: str
    message: str


@bp.get("/ping")
def pong():
    """
    Health check endpoint to verify API and database connectivity.

    Returns the current status of the API and database connection.
    """
    session = get_db()
    try:
        # Verify database connection by executing a simple query
        session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        session.rollback()
        db_status = "disconnected"

    if db_status == "disconnected":
        payload = PingResponse(
            status="degraded",
            message="API is running but database connection is unavailable",
        )
    else:
        payload = PingResponse(
            status="healthy", message="API and database are operational"
        )
    return jsonify(payload.model_dump(mode="json"))
