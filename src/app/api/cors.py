"""CORS handling equivalent to Starlette's ``CORSMiddleware``.

flask-cors does not reproduce Starlette's exact header set, so the behaviour the
FastAPI app exhibited is implemented directly:

* preflight (OPTIONS + Origin + Access-Control-Request-Method) -> 200 with
  Allow-Origin / Allow-Methods / Allow-Headers / Allow-Credentials,
* simple request carrying an Origin -> Allow-Credentials always, Allow-Origin
  only when the origin is in the configured allowlist,
* OPTIONS/HEAD without CORS intent -> 405, matching Starlette's router.
"""

from flask import request

# Mirrors app.add_middleware(CORSMiddleware, allow_methods=[...]) ordering.
ALLOW_METHODS = ["DELETE", "GET", "POST", "PUT"]


def init_cors(app, allowed_origins):
    allowed = [origin.strip() for origin in allowed_origins if origin.strip()]

    def _origin_allowed(origin):
        return origin in allowed or "*" in allowed

    @app.before_request
    def _preflight():
        origin = request.headers.get("Origin")
        requested_method = request.headers.get("Access-Control-Request-Method")
        if request.method != "OPTIONS" or not origin or not requested_method:
            return None
        response = app.make_response("OK")
        response.headers["Content-Type"] = "text/plain; charset=utf-8"
        response.headers["Access-Control-Allow-Methods"] = ", ".join(ALLOW_METHODS)
        response.headers["Access-Control-Max-Age"] = "600"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        requested_headers = request.headers.get("Access-Control-Request-Headers")
        if requested_headers:
            response.headers["Access-Control-Allow-Headers"] = requested_headers
        response.headers["Vary"] = "Origin"
        if _origin_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
        return response

    @app.after_request
    def _simple(response):
        origin = request.headers.get("Origin")
        if not origin:
            return response
        response.headers.setdefault("Access-Control-Allow-Credentials", "true")
        if _origin_allowed(origin):
            response.headers.setdefault("Access-Control-Allow-Origin", origin)
            response.headers.setdefault("Vary", "Origin")
        return response
