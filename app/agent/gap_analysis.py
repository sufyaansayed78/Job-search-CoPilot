"""
Job-description gap analysis agent

Two nodes, run in sequence:

  extract_requirements_node
      Raw job description text -> structured requirements
      (required skills, nice-to-have skills, min years experience, seniority)

  compare_to_resume_node
      Structured requirements + the user's resume text -> match score,
      matched/missing skills, a strong_fit/stretch/skip recommendation,
      and a short summary of what to emphasise in the application.

Splitting extraction from comparison (rather than one big prompt) means each
step's output is independently inspectable and testable, and the extracted
requirements can be reused/cached if the same JD is re-analysed later.
"""

from typing import TypedDict, Literal
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from app.config import settings




class ExtractedRequirements(BaseModel):
    required_skills: list[str] = Field(description="Must-have skills/technologies")
    nice_to_have_skills: list[str] = Field(default_factory=list)
    min_years_experience: int = Field(default=0)
    seniority_level: str = Field(description="e.g. junior, mid, senior, staff")


class GapAnalysisResult(BaseModel):
    match_score: float = Field(description="0-100 fit score", ge=0, le=100)
    matched_skills: list[str]
    missing_skills: list[str]
    recommendation: Literal["strong_fit", "stretch", "skip"]
    summary: str = Field(description="1-2 sentences: what to emphasise, or why to skip")


class AgentState(TypedDict):
    job_description: str
    resume_text: str
    requirements: ExtractedRequirements | None
    result: GapAnalysisResult | None


def _get_llm():
    return ChatAnthropic(
        model=settings.ANTHROPIC_MODEL,
        api_key=settings.ANTHROPIC_API_KEY,
        temperature=0,
    )


def extract_requirements_node(state: AgentState) -> AgentState:
    llm = _get_llm().with_structured_output(ExtractedRequirements)
    result = llm.invoke(
        "Extract the hiring requirements from this job description. "
        "Separate must-have skills from nice-to-have ones. If years of "
        "experience isn't stated, estimate conservatively from the seniority "
        f"implied by the language.\n\nJob description:\n{state['job_description']}"
    )
    return {**state, "requirements": result}


def compare_to_resume_node(state: AgentState) -> AgentState:
    reqs = state["requirements"]
    llm = _get_llm().with_structured_output(GapAnalysisResult)
    result = llm.invoke(
        "Compare this candidate's resume against the extracted job requirements. "
        "Be honest and specific — don't inflate the match score to be encouraging. "
        "A 'strong_fit' recommendation should mean most required skills are "
        "genuinely present; 'stretch' means a real gap exists but it's worth "
        "applying anyway; 'skip' means the gap is too large to be a good use of time.\n\n"
        f"Required skills: {reqs.required_skills}\n"
        f"Nice-to-have skills: {reqs.nice_to_have_skills}\n"
        f"Minimum years experience: {reqs.min_years_experience}\n"
        f"Seniority level: {reqs.seniority_level}\n\n"
        f"Candidate resume:\n{state['resume_text']}"
    )
    return {**state, "result": result}


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("extract_requirements", extract_requirements_node)
    graph.add_node("compare_to_resume", compare_to_resume_node)
    graph.set_entry_point("extract_requirements")
    graph.add_edge("extract_requirements", "compare_to_resume")
    graph.add_edge("compare_to_resume", END)
    return graph.compile()


_compiled_graph = None


def run_gap_analysis(job_description: str, resume_text: str) -> dict:
    """Entry point used by the Celery task. Returns a plain dict ready to
    persist as a GapAnalysis row."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()

    final_state = _compiled_graph.invoke({
        "job_description": job_description,
        "resume_text": resume_text,
        "requirements": None,
        "result": None,
    })

    reqs: ExtractedRequirements = final_state["requirements"]
    result: GapAnalysisResult = final_state["result"]

    return {
        "match_score": result.match_score,
        "matched_skills": result.matched_skills,
        "missing_skills": result.missing_skills,
        "required_skills": reqs.required_skills,
        "seniority_level": reqs.seniority_level,
        "recommendation": result.recommendation,
        "summary": result.summary,
        "model_version": settings.ANTHROPIC_MODEL,
    }
