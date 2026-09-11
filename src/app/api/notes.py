from flask import Blueprint, jsonify

from app.api import crud
from app.api.dependencies import auth_required, current_user
from app.api.errors import HTTPExc
from app.api.models import NoteDB, NoteSchema
from app.api.validation import (
    collect,
    validate_body,
    validate_notes_query,
    validate_path_id,
)
from app.db import get_db

bp = Blueprint("notes", __name__)


def _serialize(note: dict):
    return NoteDB(**note).model_dump(mode="json")


@bp.post("/")
@auth_required
def create_note():
    """Create a new note"""
    payload = validate_body(NoteSchema)
    session = get_db()
    try:
        note_id = crud.post(session, payload, owner_id=current_user().id)
        response = crud.get(session, note_id)
    except Exception as e:
        raise HTTPExc(400, f"Failed to create note: {str(e)}")
    result = jsonify(_serialize(response))
    result.status_code = 201
    return result


@bp.get("/")
@auth_required
def read_notes():
    """
    Retrieve notes with optional filtering and pagination.

    - **skip**: Number of items to skip (default: 0)
    - **limit**: Maximum items per page (default: 10, max: 100)
    - **search**: Search in title and description fields
    - **completed**: Filter by completion status (true/false)
    - **tag**: Filter notes that contain this specific tag
    """
    query = validate_notes_query()
    session = get_db()
    try:
        rows = crud.get_notes(
            session,
            owner_id=current_user().id,
            skip=query.skip,
            limit=query.limit,
            search=query.search,
            completed=query.completed,
            tag=query.tag,
        )
    except Exception as e:
        raise HTTPExc(400, f"Failed to retrieve notes: {str(e)}")
    return jsonify([_serialize(row) for row in rows])


@bp.get("/<id>")
@auth_required
def read_note(id):
    """Retrieve a specific note by ID"""
    note_id = validate_path_id(id)
    session = get_db()
    try:
        note = crud.get(session, note_id)
        if not note or note["owner_id"] != current_user().id:
            raise HTTPExc(404, f"Note with id {note_id} not found")
        return jsonify(_serialize(note))
    except HTTPExc:
        raise
    except Exception as e:
        raise HTTPExc(400, f"Failed to retrieve note: {str(e)}")


@bp.put("/<id>")
@auth_required
def update_note(id):
    """Update an existing note"""
    # FastAPI reports path and body failures together, so accumulate both.
    note_id, payload = collect(
        lambda: validate_path_id(id),
        lambda: validate_body(NoteSchema),
    )
    session = get_db()
    try:
        note = crud.get(session, note_id)
        if not note or note["owner_id"] != current_user().id:
            raise HTTPExc(404, f"Note with id {note_id} not found")
        crud.put(session, note_id, payload)
        response = crud.get(session, note_id)
        return jsonify(_serialize(response))
    except HTTPExc:
        raise
    except Exception as e:
        raise HTTPExc(400, f"Failed to update note: {str(e)}")


@bp.delete("/<id>")
@auth_required
def delete_note(id):
    """Delete a note by ID"""
    note_id = validate_path_id(id)
    session = get_db()
    try:
        note = crud.get(session, note_id)
        if not note or note["owner_id"] != current_user().id:
            raise HTTPExc(404, f"Note with id {note_id} not found")
        crud.delete_note(session, note_id)
        return jsonify(_serialize(note))
    except HTTPExc:
        raise
    except Exception as e:
        raise HTTPExc(400, f"Failed to delete note: {str(e)}")
