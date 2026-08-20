"""Request validation that reproduces FastAPI's 422 error payloads.

FastAPI validates body / path / query parameters with Pydantic and reports
failures as a list of error objects whose ``loc`` is prefixed with the
parameter source (``body``, ``path``, ``query``). Flask does none of this, so
the same Pydantic models are driven manually here and their errors are
reshaped into the identical envelope.
"""

from typing import Optional, Type

from flask import request
from pydantic import BaseModel, Field, ValidationError

from app.api.errors import RequestValidationError


def _jsonable(value):
    """Make a pydantic ``ctx`` value JSON-serialisable (some hold exceptions)."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def to_fastapi_errors(exc: ValidationError, source: str) -> list:
    """Reshape pydantic errors into FastAPI's ``detail`` list."""
    errors = []
    for err in exc.errors():
        item = {
            "type": err["type"],
            "loc": [source, *[str(part) for part in err["loc"]]],
            "msg": err["msg"],
            "input": _jsonable(err.get("input")),
        }
        if err.get("ctx"):
            item["ctx"] = _jsonable(err["ctx"])
        errors.append(item)
    return errors


def validate_body(model: Type[BaseModel]) -> BaseModel:
    """Parse and validate the JSON body, raising FastAPI-shaped 422s."""
    try:
        payload = request.get_json(silent=True)
    except Exception:
        payload = None
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise RequestValidationError(
            [
                {
                    "type": "model_attributes_type",
                    "loc": ["body"],
                    "msg": "Input should be a valid dictionary or object to extract fields from",
                    "input": payload,
                }
            ]
        )
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise RequestValidationError(to_fastapi_errors(exc, "body")) from exc


class _PathId(BaseModel):
    id: int = Field(gt=0)


def validate_path_id(raw_id: str) -> int:
    """Validate the ``{id}`` path parameter (``Path(..., gt=0)`` in FastAPI)."""
    try:
        return _PathId.model_validate({"id": raw_id}).id
    except ValidationError as exc:
        raise RequestValidationError(to_fastapi_errors(exc, "path")) from exc


class NotesQuery(BaseModel):
    """Mirrors the Query(...) declarations on ``read_notes``."""

    skip: int = Field(0, ge=0)
    limit: int = Field(10, ge=1, le=100)
    search: Optional[str] = Field(None, max_length=100)
    completed: Optional[bool] = None
    tag: Optional[str] = None


def validate_notes_query() -> NotesQuery:
    """Validate the notes list query string, raising FastAPI-shaped 422s."""
    # Only pass through keys the client actually sent so declared defaults apply.
    supplied = {
        key: request.args.get(key)
        for key in ("skip", "limit", "search", "completed", "tag")
        if key in request.args
    }
    try:
        return NotesQuery.model_validate(supplied)
    except ValidationError as exc:
        raise RequestValidationError(to_fastapi_errors(exc, "query")) from exc


def validate_login_form() -> tuple:
    """Validate the OAuth2 password-grant form fields.

    FastAPI's ``OAuth2PasswordRequestForm`` reports absent form fields as
    ``{"type": "missing", "input": null}`` rather than as a pydantic string
    error, so the errors are constructed directly to match.
    """
    errors = []
    values = {}
    for field in ("username", "password"):
        value = request.form.get(field)
        if value is None:
            errors.append(
                {
                    "type": "missing",
                    "loc": ["body", field],
                    "msg": "Field required",
                    "input": None,
                }
            )
        else:
            values[field] = value
    if errors:
        raise RequestValidationError(errors)
    return values["username"], values["password"]


def collect(*validators):
    """Run several validators and merge their errors into one 422.

    FastAPI validates path, query and body in a single pass and reports every
    failure in one ``detail`` list, so callers with more than one parameter
    source must accumulate rather than raise on the first failure.
    """
    results, errors = [], []
    for validator in validators:
        try:
            results.append(validator())
        except RequestValidationError as exc:
            results.append(None)
            errors.extend(exc.errors)
    if errors:
        raise RequestValidationError(errors)
    return results
