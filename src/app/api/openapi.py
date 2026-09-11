"""OpenAPI document and Swagger UI.

FastAPI served ``/openapi.json`` and ``/docs`` out of the box. Flask does not,
so the schema is generated from the same Pydantic models and served alongside a
Swagger UI page (FastAPI's own /docs also loads Swagger UI from a CDN, so the
delivery mechanism is unchanged).
"""

from flask import Blueprint, jsonify

from app.api.models import (
    ErrorResponse,
    NoteDB,
    NoteSchema,
    Token,
    UserCreate,
    UserDB,
)
from app.api.ping import PingResponse
from app.api.validation import NotesQuery

bp = Blueprint("openapi", __name__)

TITLE = "Notes API"
DESCRIPTION = "A simple API for managing notes with search and filtering"
VERSION = "1.0.0"

_MODELS = {
    "PingResponse": PingResponse,
    "UserCreate": UserCreate,
    "UserDB": UserDB,
    "Token": Token,
    "NoteSchema": NoteSchema,
    "NoteDB": NoteDB,
    "ErrorResponse": ErrorResponse,
    "NotesQuery": NotesQuery,
}


def _schemas():
    schemas = {}
    for name, model in _MODELS.items():
        schema = model.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )
        schemas.update(schema.pop("$defs", {}))
        schemas[name] = schema
    schemas["ValidationError"] = {
        "title": "ValidationError",
        "type": "object",
        "properties": {
            "loc": {
                "title": "Location",
                "type": "array",
                "items": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
            },
            "msg": {"title": "Message", "type": "string"},
            "type": {"title": "Error Type", "type": "string"},
        },
        "required": ["loc", "msg", "type"],
    }
    schemas["HTTPValidationError"] = {
        "title": "HTTPValidationError",
        "type": "object",
        "properties": {
            "detail": {
                "title": "Detail",
                "type": "array",
                "items": {"$ref": "#/components/schemas/ValidationError"},
            }
        },
    }
    return schemas


def _json_body(ref, required=True):
    return {
        "required": required,
        "content": {"application/json": {"schema": {"$ref": ref}}},
    }


def _json_response(description, ref=None, is_array=False):
    if ref is None:
        return {"description": description}
    schema = (
        {"type": "array", "items": {"$ref": ref}} if is_array else {"$ref": ref}
    )
    return {"description": description, "content": {"application/json": {"schema": schema}}}


_VALIDATION_RESPONSE = _json_response(
    "Validation Error", "#/components/schemas/HTTPValidationError"
)
_ERROR_REF = "#/components/schemas/ErrorResponse"
_NOTE_REF = "#/components/schemas/NoteDB"

_ID_PARAM = {
    "name": "id",
    "in": "path",
    "required": True,
    "schema": {"type": "integer", "exclusiveMinimum": 0, "title": "Id"},
    "description": "Note ID",
}


def build_spec():
    return {
        "openapi": "3.1.0",
        "info": {"title": TITLE, "description": DESCRIPTION, "version": VERSION},
        "paths": {
            "/ping": {
                "get": {
                    "tags": ["health"],
                    "summary": "Health check endpoint",
                    "operationId": "pong_ping_get",
                    "responses": {
                        "200": _json_response(
                            "Successful Response",
                            "#/components/schemas/PingResponse",
                        )
                    },
                }
            },
            "/auth/register": {
                "post": {
                    "tags": ["auth"],
                    "summary": "Register",
                    "operationId": "register_auth_register_post",
                    "requestBody": _json_body("#/components/schemas/UserCreate"),
                    "responses": {
                        "201": _json_response(
                            "Successful Response", "#/components/schemas/UserDB"
                        ),
                        "400": _json_response("Bad Request", _ERROR_REF),
                        "422": _VALIDATION_RESPONSE,
                    },
                }
            },
            "/auth/token": {
                "post": {
                    "tags": ["auth"],
                    "summary": "Login For Access Token",
                    "operationId": "login_for_access_token_auth_token_post",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/x-www-form-urlencoded": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "username": {"type": "string"},
                                        "password": {
                                            "type": "string",
                                            "format": "password",
                                        },
                                    },
                                    "required": ["username", "password"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": _json_response(
                            "Successful Response", "#/components/schemas/Token"
                        ),
                        "422": _VALIDATION_RESPONSE,
                    },
                }
            },
            "/notes/": {
                "get": {
                    "tags": ["notes"],
                    "summary": "Read Notes",
                    "operationId": "read_notes_notes__get",
                    "security": [{"OAuth2PasswordBearer": []}],
                    "parameters": [
                        {
                            "name": "skip",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "minimum": 0, "default": 0},
                            "description": "Number of items to skip",
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 100,
                                "default": 10,
                            },
                            "description": "Maximum number of items to return",
                        },
                        {
                            "name": "search",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string", "maxLength": 100},
                            "description": "Search term for title/description",
                        },
                        {
                            "name": "completed",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "boolean"},
                            "description": "Filter by completion status",
                        },
                        {
                            "name": "tag",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                            "description": "Filter by tag",
                        },
                    ],
                    "responses": {
                        "200": _json_response(
                            "Successful Response", _NOTE_REF, is_array=True
                        ),
                        "400": _json_response("Bad Request", _ERROR_REF),
                        "422": _VALIDATION_RESPONSE,
                    },
                },
                "post": {
                    "tags": ["notes"],
                    "summary": "Create Note",
                    "operationId": "create_note_notes__post",
                    "security": [{"OAuth2PasswordBearer": []}],
                    "requestBody": _json_body("#/components/schemas/NoteSchema"),
                    "responses": {
                        "201": _json_response("Successful Response", _NOTE_REF),
                        "400": _json_response("Bad Request", _ERROR_REF),
                        "422": _VALIDATION_RESPONSE,
                    },
                },
            },
            "/notes/{id}": {
                "get": {
                    "tags": ["notes"],
                    "summary": "Read Note",
                    "operationId": "read_note_notes__id__get",
                    "security": [{"OAuth2PasswordBearer": []}],
                    "parameters": [_ID_PARAM],
                    "responses": {
                        "200": _json_response("Successful Response", _NOTE_REF),
                        "404": _json_response("Not Found", _ERROR_REF),
                        "422": _VALIDATION_RESPONSE,
                    },
                },
                "put": {
                    "tags": ["notes"],
                    "summary": "Update Note",
                    "operationId": "update_note_notes__id__put",
                    "security": [{"OAuth2PasswordBearer": []}],
                    "parameters": [_ID_PARAM],
                    "requestBody": _json_body("#/components/schemas/NoteSchema"),
                    "responses": {
                        "200": _json_response("Successful Response", _NOTE_REF),
                        "404": _json_response("Not Found", _ERROR_REF),
                        "422": _VALIDATION_RESPONSE,
                    },
                },
                "delete": {
                    "tags": ["notes"],
                    "summary": "Delete Note",
                    "operationId": "delete_note_notes__id__delete",
                    "security": [{"OAuth2PasswordBearer": []}],
                    "parameters": [_ID_PARAM],
                    "responses": {
                        "200": _json_response("Successful Response", _NOTE_REF),
                        "404": _json_response("Not Found", _ERROR_REF),
                        "422": _VALIDATION_RESPONSE,
                    },
                },
            },
        },
        "components": {
            "schemas": _schemas(),
            "securitySchemes": {
                "OAuth2PasswordBearer": {
                    "type": "oauth2",
                    "flows": {"password": {"scopes": {}, "tokenUrl": "auth/token"}},
                }
            },
        },
    }


@bp.get("/openapi.json")
def openapi_json():
    return jsonify(build_spec())


_SWAGGER_HTML = """<!DOCTYPE html>
<html>
<head>
<link type="text/css" rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
<title>%(title)s - Swagger UI</title>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
const ui = SwaggerUIBundle({
    url: '/openapi.json',
    dom_id: '#swagger-ui',
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
    layout: "BaseLayout",
    deepLinking: true,
    showExtensions: true,
    showCommonExtensions: true,
})
</script>
</body>
</html>""" % {"title": TITLE}


@bp.get("/docs")
def swagger_ui():
    return _SWAGGER_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}
