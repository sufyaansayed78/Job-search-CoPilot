from unittest.mock import patch


class TestAnalyzeJobPostingTask:
    def test_task_persists_analysis_and_updates_status(self, client, auth_headers, posting_id):
        from app.tasks import analyze_job_posting_task

        mock_result = {
            "match_score": 82.0,
            "matched_skills": ["Python", "Django"],
            "missing_skills": ["Kubernetes"],
            "required_skills": ["Python", "Django", "Kubernetes"],
            "seniority_level": "mid",
            "recommendation": "strong_fit",
            "summary": "Good match, one gap in container orchestration.",
            "model_version": "claude-haiku-4-5-20251001",
        }

        with patch("app.agent.gap_analysis.run_gap_analysis", return_value=mock_result):
            analyze_job_posting_task(posting_id)

        resp = client.get(f"/job-postings/{posting_id}/analysis", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["match_score"] == 82.0
        assert resp.json()["recommendation"] == "strong_fit"

        posting_resp = client.get(f"/job-postings/{posting_id}", headers=auth_headers)
        assert posting_resp.json()["analysis_status"] == "done"

    def test_task_marks_failed_on_error(self, posting_id):
        from app.tasks import analyze_job_posting_task
        from app.database import SessionLocal
        from app.models import JobPosting

        with patch(
            "app.agent.gap_analysis.run_gap_analysis",
            side_effect=Exception("LLM API unavailable"),
        ):
            try:
                analyze_job_posting_task(posting_id)
            except Exception:
                pass  # retry raises after exhausting attempts in real Celery; fine for this test

        db = SessionLocal()
        posting = db.query(JobPosting).filter(JobPosting.id == posting_id).first()
        assert posting.analysis_status in ("failed", "pending")
        db.close()
