from flask import Flask, redirect, request
from werkzeug.routing import RequestRedirect

from app.api import auth, notes, openapi, ping
from app.api.cors import init_cors
from app.api.errors import HTTPExc, register_error_handlers
from app.db import close_db, engine
from app.config import get_settings

settings = get_settings()


def create_app() -> Flask:
    app = Flask(__name__)

    # FastAPI emits response fields in model declaration order; Flask sorts JSON
    # keys by default, so that is turned off to keep payloads byte-comparable.
    app.json.sort_keys = False

    register_error_handlers(app)

    @app.before_request
    def _starlette_slash_redirect():
        """Starlette redirects a missing trailing slash with 307, Werkzeug with 308.

        Flask treats RequestRedirect as a RoutingException and returns it before
        error handlers run, so it has to be intercepted here.
        """
        exc = request.routing_exception
        if isinstance(exc, RequestRedirect):
            return redirect(exc.new_url, code=307)
        return None

    # CORS configuration - only allow specific origins in production
    allowed_origins = settings.allowed_origins.split(",")
    init_cors(app, allowed_origins)

    @app.before_request
    def _reject_implicit_methods():
        """Starlette does not auto-register HEAD/OPTIONS for GET routes.

        Werkzeug does, so requests Starlette answered with 405 would otherwise
        succeed. Non-CORS HEAD/OPTIONS are rejected here to preserve behaviour.
        """
        if request.method not in ("HEAD", "OPTIONS"):
            return None
        if request.headers.get("Origin") and request.headers.get(
            "Access-Control-Request-Method"
        ):
            return None  # CORS preflight, handled by init_cors
        rule = request.url_rule
        if rule is None:
            return None
        explicit = sorted(rule.methods - {"HEAD", "OPTIONS"})
        if request.method not in explicit:
            raise HTTPExc(405, "Method Not Allowed", {"Allow": ", ".join(explicit)})
        return None

    app.teardown_appcontext(close_db)

    app.register_blueprint(ping.bp)
    app.register_blueprint(openapi.bp)
    app.register_blueprint(auth.bp, url_prefix="/auth")
    app.register_blueprint(notes.bp, url_prefix="/notes")

    return app


app = create_app()
