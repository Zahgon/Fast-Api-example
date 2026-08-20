"""Error types and handlers that reproduce FastAPI's HTTP error envelopes.

FastAPI serialises ``HTTPException`` as ``{"detail": ...}`` and request
validation failures as ``{"detail": [ ...pydantic errors... ]}`` with status
422. Flask has no equivalent, so both shapes are rebuilt here and registered as
application-wide error handlers.
"""

from flask import jsonify


class HTTPExc(Exception):
    """Direct replacement for ``fastapi.HTTPException``."""

    def __init__(self, status_code: int, detail, headers: dict | None = None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.headers = headers or {}


class RequestValidationError(Exception):
    """Direct replacement for FastAPI's ``RequestValidationError`` (HTTP 422)."""

    def __init__(self, errors: list):
        super().__init__("validation error")
        self.errors = errors


def _json(payload, status, headers=None):
    response = jsonify(payload)
    response.status_code = status
    for key, value in (headers or {}).items():
        response.headers[key] = value
    return response


def register_error_handlers(app):
    @app.errorhandler(HTTPExc)
    def _http_exc(exc: HTTPExc):
        return _json({"detail": exc.detail}, exc.status_code, exc.headers)

    @app.errorhandler(RequestValidationError)
    def _validation_exc(exc: RequestValidationError):
        return _json({"detail": exc.errors}, 422)

    @app.errorhandler(404)
    def _not_found(_exc):
        # Starlette's default 404 body
        return _json({"detail": "Not Found"}, 404)

    @app.errorhandler(405)
    def _method_not_allowed(exc):
        # Starlette's default 405 body; preserve the Allow header Werkzeug computed
        headers = {}
        valid = getattr(exc, "valid_methods", None)
        if valid:
            # Starlette never registers implicit HEAD/OPTIONS, so they must not
            # appear in Allow either.
            explicit = sorted(set(valid) - {"HEAD", "OPTIONS"})
            if explicit:
                headers["Allow"] = ", ".join(explicit)
        return _json({"detail": "Method Not Allowed"}, 405, headers)

    @app.errorhandler(500)
    def _internal(_exc):
        return _json({"detail": "Internal Server Error"}, 500)
