from datetime import datetime, timedelta, timezone


class TestApplications:
    def test_create_application(self, client, auth_headers, posting_id):
        resp = client.post(
            "/applications/",
            json={"job_posting_id": posting_id, "resume_version": "backend-v2"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "wishlist"

    def test_status_update_sets_applied_date(self, client, auth_headers, posting_id):
        create_resp = client.post(
            "/applications/", json={"job_posting_id": posting_id}, headers=auth_headers,
        )
        app_id = create_resp.json()["id"]

        resp = client.patch(
            f"/applications/{app_id}/status", json={"status": "applied"}, headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["applied_date"] is not None

    def test_upcoming_follow_ups(self, client, auth_headers, posting_id):
        create_resp = client.post(
            "/applications/", json={"job_posting_id": posting_id}, headers=auth_headers,
        )
        app_id = create_resp.json()["id"]
        soon = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

        client.patch(
            f"/applications/{app_id}/status",
            json={"status": "applied", "follow_up_date": soon},
            headers=auth_headers,
        )
        resp = client.get("/applications/upcoming-follow-ups", headers=auth_headers)
        assert resp.status_code == 200
        ids = [a["id"] for a in resp.json()]
        assert app_id in ids

    def test_far_future_follow_up_excluded(self, client, auth_headers, posting_id):
        create_resp = client.post(
            "/applications/", json={"job_posting_id": posting_id}, headers=auth_headers,
        )
        app_id = create_resp.json()["id"]
        far = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()

        client.patch(
            f"/applications/{app_id}/status",
            json={"status": "applied", "follow_up_date": far},
            headers=auth_headers,
        )
        resp = client.get("/applications/upcoming-follow-ups?within_days=7", headers=auth_headers)
        ids = [a["id"] for a in resp.json()]
        assert app_id not in ids


class TestDashboard:
    def test_stats_shape(self, client, auth_headers, posting_id):
        client.post("/applications/", json={"job_posting_id": posting_id}, headers=auth_headers)
        resp = client.get("/dashboard/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_applications" in data
        assert "by_status" in data
        assert "response_rate_pct" in data

    def test_response_rate_excludes_wishlist(self, client, auth_headers, posting_id):
        create_resp = client.post(
            "/applications/", json={"job_posting_id": posting_id}, headers=auth_headers,
        )
        app_id = create_resp.json()["id"]
        client.patch(f"/applications/{app_id}/status", json={"status": "applied"}, headers=auth_headers)

        resp = client.get("/dashboard/stats", headers=auth_headers)
        # One applied, zero responded yet -> 0% response rate, not skewed by wishlist entries
        assert resp.json()["response_rate_pct"] == 0.0
