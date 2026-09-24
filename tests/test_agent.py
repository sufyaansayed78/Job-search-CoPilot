from unittest.mock import patch, MagicMock
from app.agent.gap_analysis import (
    run_gap_analysis, ExtractedRequirements, GapAnalysisResult, build_graph,
)


def _mock_llm_sequence(extracted: ExtractedRequirements, result: GapAnalysisResult):
    """Two calls to with_structured_output().invoke() happen per run:
    first extraction, then comparison. Mock ChatAnthropic so no real API
    call or key is needed."""
    mock_extract_llm = MagicMock()
    mock_extract_llm.invoke.return_value = extracted

    mock_compare_llm = MagicMock()
    mock_compare_llm.invoke.return_value = result

    mock_base_llm = MagicMock()
    mock_base_llm.with_structured_output.side_effect = [mock_extract_llm, mock_compare_llm]
    return mock_base_llm


class TestGraphStructure:
    def test_graph_compiles(self):
        graph = build_graph()
        assert graph is not None

    def test_graph_has_two_nodes(self):
        graph = build_graph()
        node_names = set(graph.get_graph().nodes.keys())
        assert "extract_requirements" in node_names
        assert "compare_to_resume" in node_names


class TestRunGapAnalysis:
    @patch("app.agent.gap_analysis._get_llm")
    def test_strong_fit_flows_through(self, mock_get_llm):
        extracted = ExtractedRequirements(
            required_skills=["Python", "Django", "PostgreSQL"],
            nice_to_have_skills=["AWS"],
            min_years_experience=3,
            seniority_level="mid",
        )
        result = GapAnalysisResult(
            match_score=88.0,
            matched_skills=["Python", "Django", "PostgreSQL"],
            missing_skills=[],
            recommendation="strong_fit",
            summary="Strong match on all required backend skills.",
        )
        mock_get_llm.return_value = _mock_llm_sequence(extracted, result)

        output = run_gap_analysis(
            job_description="Need a Django backend engineer with PostgreSQL experience.",
            resume_text="3 years building Django REST APIs with PostgreSQL.",
        )

        assert output["match_score"] == 88.0
        assert output["recommendation"] == "strong_fit"
        assert "Python" in output["matched_skills"]
        assert output["required_skills"] == ["Python", "Django", "PostgreSQL"]

    @patch("app.agent.gap_analysis._get_llm")
    def test_skip_recommendation_flows_through(self, mock_get_llm):
        extracted = ExtractedRequirements(
            required_skills=["Kubernetes", "Go", "10+ years distributed systems"],
            nice_to_have_skills=[],
            min_years_experience=10,
            seniority_level="staff",
        )
        result = GapAnalysisResult(
            match_score=12.0,
            matched_skills=[],
            missing_skills=["Kubernetes", "Go", "10+ years distributed systems"],
            recommendation="skip",
            summary="Large experience and stack gap for a staff-level role.",
        )
        mock_get_llm.return_value = _mock_llm_sequence(extracted, result)

        output = run_gap_analysis(
            job_description="Staff engineer, 10+ years, Go, Kubernetes at massive scale.",
            resume_text="1 year Python internship experience.",
        )

        assert output["recommendation"] == "skip"
        assert output["match_score"] < 50

    @patch("app.agent.gap_analysis._get_llm")
    def test_output_includes_model_version(self, mock_get_llm):
        extracted = ExtractedRequirements(
            required_skills=["Python"], nice_to_have_skills=[],
            min_years_experience=1, seniority_level="junior",
        )
        result = GapAnalysisResult(
            match_score=70.0, matched_skills=["Python"], missing_skills=[],
            recommendation="stretch", summary="Reasonable fit.",
        )
        mock_get_llm.return_value = _mock_llm_sequence(extracted, result)

        output = run_gap_analysis(job_description="Python role.", resume_text="Some Python.")
        assert "model_version" in output
        assert len(output["model_version"]) > 0
