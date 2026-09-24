class TestRegistration:
    def test_register_success(self, client):
        resp = client.post("/auth/register", json={
            "username": "newuser", "email": "new@copilot.com", "password": "Secure123!",
        })
        assert resp.status_code == 201
        assert resp.json()["email"] == "new@copilot.com"

    def test_duplicate_email_rejected(self, client):
        client.post("/auth/register", json={
            "username": "dup1", "email": "dup@copilot.com", "password": "Secure123!",
        })
        resp = client.post("/auth/register", json={
            "username": "dup2", "email": "dup@copilot.com", "password": "Secure123!",
        })
        assert resp.status_code == 400

    def test_short_password_rejected(self, client):
        resp = client.post("/auth/register", json={
            "username": "shortpw", "email": "short@copilot.com", "password": "abc",
        })
        assert resp.status_code == 400


class TestLoginAndProfile:
    def test_login_success(self, client):
        client.post("/auth/register", json={
            "username": "loginuser", "email": "login@copilot.com", "password": "Secure123!",
        })
        resp = client.post("/auth/token", data={
            "username": "login@copilot.com", "password": "Secure123!",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_wrong_password_rejected(self, client):
        client.post("/auth/register", json={
            "username": "wrongpw", "email": "wrongpw@copilot.com", "password": "Correct123!",
        })
        resp = client.post("/auth/token", data={
            "username": "wrongpw@copilot.com", "password": "Wrong123!",
        })
        assert resp.status_code == 401

    def test_unauthenticated_blocked(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_update_resume(self, client, auth_headers):
        resp = client.put(
            "/auth/me/resume",
            json={"resume_text": "5 years Python, Django, PostgreSQL, AWS SAA certified."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "Django" in resp.json()["resume_text"]
