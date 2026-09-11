"""
Comprehensive tests for the Notes API endpoints
"""

import pytest


def _create(client, headers, **overrides):
    payload = {
        "title": "something",
        "description": "something else",
        "completed": False,
        "tags": [],
    }
    payload.update(overrides)
    return client.post("/notes/", json=payload, headers=headers)


class TestAuthorization:
    """Every notes route is behind the bearer token"""

    @pytest.mark.parametrize(
        "method, path",
        [
            ("get", "/notes/"),
            ("post", "/notes/"),
            ("get", "/notes/1"),
            ("put", "/notes/1"),
            ("delete", "/notes/1"),
        ],
    )
    def test_requires_token(self, test_app, method, path):
        response = getattr(test_app, method)(path)
        assert response.status_code == 401
        assert response.get_json()["detail"] == "Not authenticated"
        assert response.headers.get("WWW-Authenticate") == "Bearer"

    def test_rejects_bad_token(self, test_app):
        response = test_app.get(
            "/notes/", headers={"Authorization": "Bearer not.a.real.token"}
        )
        assert response.status_code == 401
        assert response.get_json()["detail"] == "Could not validate credentials"


class TestCreateNote:
    """Tests for creating notes"""

    def test_create_note_success(self, test_app, token_headers):
        """Test successful note creation"""
        response = _create(
            test_app, token_headers, title="something", tags=["work"]
        )
        assert response.status_code == 201

        body = response.get_json()
        assert body["title"] == "something"
        assert body["description"] == "something else"
        assert body["completed"] is False
        assert body["is_deleted"] is False
        assert body["tags"] == ["work"]
        assert body["id"] > 0
        assert "created_date" in body and "owner_id" in body

    @pytest.mark.parametrize(
        "test_payload, expected_status",
        [
            ({}, 422),  # Missing required fields
            ({"description": "bar"}, 422),  # Missing title
            (
                {"title": "foo", "description": "bar", "completed": True, "tags": []},
                201,
            ),  # Valid
            ({"title": "1", "description": "bar"}, 422),  # Title too short
            ({"title": "foo", "description": "1"}, 422),  # Description too short
            ({"title": "   ", "description": "bar"}, 422),  # Blank title
            ({"title": "foo", "description": "   "}, 422),  # Blank description
            ({"title": "x" * 256, "description": "bar"}, 422),  # Title too long
            ({"title": "foo", "description": "x" * 1001}, 422),  # Description too long
        ],
    )
    def test_create_note_validation(
        self, test_app, token_headers, test_payload, expected_status
    ):
        """Test note creation with invalid payloads"""
        response = test_app.post("/notes/", json=test_payload, headers=token_headers)
        assert response.status_code == expected_status


class TestReadNotes:
    """Tests for reading notes"""

    def test_read_single_note(self, test_app, token_headers):
        """Test reading a single note by ID"""
        created = _create(test_app, token_headers).get_json()

        response = test_app.get(f"/notes/{created['id']}", headers=token_headers)
        assert response.status_code == 200
        assert response.get_json() == created

    def test_read_note_not_found(self, test_app, token_headers):
        """Test reading non-existent note returns 404"""
        response = test_app.get("/notes/999", headers=token_headers)
        assert response.status_code == 404
        assert "not found" in response.get_json()["detail"].lower()

    def test_read_note_invalid_id(self, test_app, token_headers):
        """Test reading note with invalid ID"""
        assert test_app.get("/notes/0", headers=token_headers).status_code == 422
        assert test_app.get("/notes/invalid", headers=token_headers).status_code == 422

    def test_read_all_notes(self, test_app, token_headers):
        """Test reading all notes with default pagination"""
        _create(test_app, token_headers, title="note 1", description="desc 1",
                tags=["work"])
        _create(test_app, token_headers, title="note 2", description="desc 2")

        response = test_app.get("/notes/", headers=token_headers)
        assert response.status_code == 200
        assert len(response.get_json()) == 2

    def test_read_notes_with_pagination(self, test_app, token_headers):
        """Test note pagination with skip and limit"""
        _create(test_app, token_headers, title="note 1", description="desc 1")
        _create(test_app, token_headers, title="note 2", description="desc 2")

        response = test_app.get("/notes/?skip=0&limit=1", headers=token_headers)
        assert response.status_code == 200
        assert len(response.get_json()) == 1

    def test_read_notes_pagination_invalid_limit(self, test_app, token_headers):
        """Test that limit exceeding maximum is rejected"""
        assert (
            test_app.get("/notes/?limit=101", headers=token_headers).status_code == 422
        )
        assert test_app.get("/notes/?limit=0", headers=token_headers).status_code == 422
        assert test_app.get("/notes/?skip=-1", headers=token_headers).status_code == 422

    def test_read_notes_filter_by_completion(self, test_app, token_headers):
        """Test filtering notes by completion status"""
        _create(test_app, token_headers, title="done note", completed=True)
        _create(test_app, token_headers, title="open note", completed=False)

        response = test_app.get("/notes/?completed=true", headers=token_headers)
        assert response.status_code == 200
        body = response.get_json()
        assert len(body) == 1
        assert body[0]["completed"] is True

    def test_read_notes_search(self, test_app, token_headers):
        """Test searching notes by title/description"""
        _create(test_app, token_headers, title="unique title", description="desc 1")
        _create(test_app, token_headers, title="other title", description="desc 2")

        response = test_app.get("/notes/?search=unique", headers=token_headers)
        assert response.status_code == 200
        body = response.get_json()
        assert len(body) == 1
        assert "unique" in body[0]["title"].lower()

    def test_read_notes_filter_by_tag(self, test_app, token_headers):
        """Test filtering notes by tag"""
        _create(test_app, token_headers, title="tagged note", tags=["alpha"])
        _create(test_app, token_headers, title="plain note", tags=["beta"])

        response = test_app.get("/notes/?tag=alpha", headers=token_headers)
        assert response.status_code == 200
        assert len(response.get_json()) == 1
        assert test_app.get(
            "/notes/?tag=nosuchtag", headers=token_headers
        ).get_json() == []

    def test_read_notes_combined_filters(self, test_app, token_headers):
        """Test combining search and completion filters"""
        _create(test_app, token_headers, title="test note", completed=True)
        _create(test_app, token_headers, title="test other", completed=False)

        response = test_app.get(
            "/notes/?search=test&completed=true", headers=token_headers
        )
        assert response.status_code == 200
        assert len(response.get_json()) == 1

    def test_notes_are_scoped_to_owner(
        self, test_app, token_headers, second_token_headers
    ):
        """A user must not see or fetch another user's notes"""
        mine = _create(test_app, token_headers, title="private note").get_json()

        assert test_app.get("/notes/", headers=second_token_headers).get_json() == []
        response = test_app.get(
            f"/notes/{mine['id']}", headers=second_token_headers
        )
        assert response.status_code == 404


class TestUpdateNote:
    """Tests for updating notes"""

    def test_update_note_success(self, test_app, token_headers):
        """Test successful note update"""
        created = _create(test_app, token_headers).get_json()
        update = {
            "title": "updated title",
            "description": "updated description",
            "completed": True,
            "tags": ["personal"],
        }

        response = test_app.put(
            f"/notes/{created['id']}", json=update, headers=token_headers
        )
        assert response.status_code == 200

        body = response.get_json()
        assert body["title"] == "updated title"
        assert body["description"] == "updated description"
        assert body["completed"] is True
        assert body["tags"] == ["personal"]
        assert body["id"] == created["id"]

    def test_update_note_not_found(self, test_app, token_headers):
        """Test updating non-existent note returns 404"""
        response = test_app.put(
            "/notes/999",
            json={"title": "foo", "description": "bar"},
            headers=token_headers,
        )
        assert response.status_code == 404

    @pytest.mark.parametrize(
        "id, payload, expected_status",
        [
            (1, {}, 422),  # Missing fields
            (1, {"description": "bar"}, 422),  # Missing title
            (999, {"title": "foo", "description": "bar"}, 404),  # Not found
            (1, {"title": "1", "description": "bar"}, 422),  # Title too short
            (1, {"title": "foo", "description": "1"}, 422),  # Description too short
            (1, {"title": "   ", "description": "bar"}, 422),  # Blank title
            (1, {"title": "foo", "description": "   "}, 422),  # Blank description
            (0, {"title": "foo", "description": "bar"}, 422),  # Invalid ID
        ],
    )
    def test_update_note_validation(
        self, test_app, token_headers, id, payload, expected_status
    ):
        """Test note update with invalid data"""
        existing = _create(test_app, token_headers).get_json()
        target = existing["id"] if id == 1 else id

        response = test_app.put(
            f"/notes/{target}", json=payload, headers=token_headers
        )
        assert response.status_code == expected_status


class TestDeleteNote:
    """Tests for deleting notes"""

    def test_delete_note_success(self, test_app, token_headers):
        """Test successful note deletion"""
        created = _create(test_app, token_headers).get_json()

        response = test_app.delete(f"/notes/{created['id']}", headers=token_headers)
        assert response.status_code == 200
        assert response.get_json() == created

    def test_delete_note_not_found(self, test_app, token_headers):
        """Test deleting non-existent note returns 404"""
        response = test_app.delete("/notes/999", headers=token_headers)
        assert response.status_code == 404
        assert "not found" in response.get_json()["detail"].lower()

    def test_delete_note_invalid_id(self, test_app, token_headers):
        """Test deleting with invalid ID"""
        assert test_app.delete("/notes/0", headers=token_headers).status_code == 422
        assert (
            test_app.delete("/notes/invalid", headers=token_headers).status_code == 422
        )

    def test_delete_note_already_deleted(self, test_app, token_headers):
        """Test that already soft-deleted note cannot be deleted again (regression)"""
        created = _create(test_app, token_headers).get_json()
        assert (
            test_app.delete(f"/notes/{created['id']}", headers=token_headers).status_code
            == 200
        )

        response = test_app.delete(f"/notes/{created['id']}", headers=token_headers)
        assert response.status_code == 404
        assert "not found" in response.get_json()["detail"].lower()

    def test_deleted_note_is_hidden(self, test_app, token_headers):
        """Soft-deleted notes disappear from reads and listings"""
        created = _create(test_app, token_headers).get_json()
        test_app.delete(f"/notes/{created['id']}", headers=token_headers)

        assert (
            test_app.get(f"/notes/{created['id']}", headers=token_headers).status_code
            == 404
        )
        assert test_app.get("/notes/", headers=token_headers).get_json() == []
