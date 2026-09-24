class TestCompanies:
    def test_create_company(self, client, auth_headers):
        resp = client.post("/companies/", json={"name": "Globex"}, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["name"] == "Globex"

    def test_list_companies_scoped_to_user(self, client, auth_headers, company_id):
        resp = client.get("/companies/", headers=auth_headers)
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.json()]
        assert company_id in ids

    def test_unauthenticated_blocked(self, client):
        resp = client.get("/companies/")
        assert resp.status_code == 401


class TestJobPostings:
    def test_create_posting(self, client, auth_headers, company_id):
        resp = client.post(
            "/job-postings/",
            json={
                "company_id": company_id,
                "title": "Senior Backend Engineer",
                "raw_description": "5+ years Django, PostgreSQL, AWS.",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["analysis_status"] == "not_started"

    def test_posting_requires_own_company(self, client, auth_headers):
        import uuid
        resp = client.post(
            "/job-postings/",
            json={
                "company_id": str(uuid.uuid4()),
                "title": "Ghost Role",
                "raw_description": "N/A",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_analysis_not_ready_returns_202(self, client, auth_headers, posting_id):
        resp = client.get(f"/job-postings/{posting_id}/analysis", headers=auth_headers)
        assert resp.status_code == 202

    def test_trigger_analysis_dispatches_task(self, client, auth_headers, posting_id):
        from unittest.mock import patch
        with patch("app.routers.job_postings.analyze_job_posting_task.delay") as mock_delay:
            resp = client.post(f"/job-postings/{posting_id}/analyze", headers=auth_headers)
            assert resp.status_code == 202
            assert mock_delay.called
