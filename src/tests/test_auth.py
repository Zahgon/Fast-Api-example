class TestAuth:
    def test_register_user_success(self, test_app):
        test_payload = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "password123",
        }

        response = test_app.post("/auth/register", json=test_payload)
        assert response.status_code == 201

        body = response.get_json()
        assert body["username"] == "newuser"
        assert body["email"] == "new@example.com"
        assert body["is_active"] is True
        assert "id" in body and "created_date" in body
        # the password must never be echoed back
        assert "password" not in body and "hashed_password" not in body

    def test_register_user_already_exists(self, test_app):
        payload = {
            "username": "existing",
            "email": "existing@example.com",
            "password": "password123",
        }
        assert test_app.post("/auth/register", json=payload).status_code == 201

        response = test_app.post("/auth/register", json=payload)
        assert response.status_code == 400
        assert "already registered" in response.get_json()["detail"].lower()

    def test_register_duplicate_email(self, test_app):
        assert (
            test_app.post(
                "/auth/register",
                json={
                    "username": "first",
                    "email": "dupe@example.com",
                    "password": "password123",
                },
            ).status_code
            == 201
        )

        response = test_app.post(
            "/auth/register",
            json={
                "username": "second",
                "email": "dupe@example.com",
                "password": "password123",
            },
        )
        assert response.status_code == 400
        assert "email already registered" in response.get_json()["detail"].lower()

    def test_register_invalid_payload(self, test_app):
        # short password and malformed email are both rejected with 422
        assert (
            test_app.post(
                "/auth/register",
                json={
                    "username": "shortpw",
                    "email": "shortpw@example.com",
                    "password": "short",
                },
            ).status_code
            == 422
        )
        assert (
            test_app.post(
                "/auth/register",
                json={
                    "username": "bademail",
                    "email": "not-an-email",
                    "password": "password123",
                },
            ).status_code
            == 422
        )

    def test_login_success(self, test_app):
        test_app.post(
            "/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "password123",
            },
        )

        response = test_app.post(
            "/auth/token",
            data={"username": "testuser", "password": "password123"},
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 200
        assert "access_token" in response.get_json()
        assert response.get_json()["token_type"] == "bearer"

    def test_login_invalid_credentials(self, test_app):
        response = test_app.post(
            "/auth/token",
            data={"username": "wrong", "password": "wrong"},
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 401

    def test_login_wrong_password(self, test_app):
        test_app.post(
            "/auth/register",
            json={
                "username": "pwuser",
                "email": "pw@example.com",
                "password": "password123",
            },
        )
        response = test_app.post(
            "/auth/token",
            data={"username": "pwuser", "password": "notthepassword"},
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 401
        assert response.headers.get("WWW-Authenticate") == "Bearer"
