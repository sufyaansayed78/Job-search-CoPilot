# Job Search Copilot

Tracks job applications and runs an LLM agent that scores each job description against your resume *before* you spend time applying — built to solve an actual problem I was living through, not a resume checklist item.

## The problem

Running 20+ live applications across LinkedIn, company sites, and referrals means losing track of status, forgetting to follow up, and worst of all applying to roles with a real skills gap without realising it until the rejection. This tracks applications properly and tells you, before you apply, whether a role is a strong fit, a stretch, or a skip.

## Architecture

```
Client
  │
  ▼
FastAPI app  ──────────────►  PostgreSQL
  │  POST /job-postings/{id}/analyze
  │  (202 Accepted, returns immediately)
  ▼
Redis (broker) ──► Celery worker ──► LangGraph agent ──► Anthropic API
                                            │
                                            ▼
                                   GapAnalysis row saved
```

## Why a LangGraph agent, not one prompt

The agent is two nodes, not one call:

1. **`extract_requirements_node`** — turns the raw pasted job description into structured requirements (required skills, nice-to-haves, minimum years, seniority level).
2. **`compare_to_resume_node`** — compares those structured requirements against your stored resume text and produces a match score, matched/missing skills, and a `strong_fit` / `stretch` / `skip` recommendation.

Splitting extraction from comparison means each step is independently testable (see `tests/test_agent.py`, which mocks each node's LLM call separately) and the extracted requirements could be cached and reused if the same JD gets re-analysed later.

**Model choice**: the agent defaults to `claude-haiku-4-5-20251001`, not a larger model. This is a background batch job, not an interactive chat — optimising for cost and throughput over the extra reasoning depth a bigger model would give is the right call here, and it's a deliberate setting (`ANTHROPIC_MODEL` in `.env`), not an oversight.

## Why the analysis is async

The LLM call for a full extract-then-compare pass takes a few seconds — too slow to hold an HTTP connection open for. `POST /job-postings/{id}/analyze` returns `202 Accepted` immediately and hands off to a Celery worker; the client polls `GET /job-postings/{id}/analysis` (also `202` until it's ready, `200` with the result once done). Same async pattern as the LoanSense project, applied to a different domain.

## Data model

- **Company** — name, website, notes
- **JobPosting** — title, pasted JD text, source, analysis status
- **Application** — status (`wishlist` → `applied` → `phone_screen` → `technical` → `onsite` → `offer`/`rejected`/`withdrawn`), resume version used, follow-up date
- **GapAnalysis** — the agent's output for a posting: match score, matched/missing skills, recommendation, summary

## API endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register |
| POST | `/auth/token` | Login, get JWT |
| PUT | `/auth/me/resume` | Set the resume text the agent compares against |
| GET/POST | `/companies/` | List / add companies |
| GET/POST | `/job-postings/` | List / add job postings (paste the JD here) |
| POST | `/job-postings/{id}/analyze` | Trigger the agent (202, async) |
| GET | `/job-postings/{id}/analysis` | Get the latest result (202 until ready) |
| GET/POST | `/applications/` | List / create applications |
| PATCH | `/applications/{id}/status` | Move an application through the pipeline |
| GET | `/applications/upcoming-follow-ups` | Applications with a follow-up due soon |
| GET | `/dashboard/stats` | Total applications, status breakdown, response rate, average match score |

## Quick start

```bash
cp .env.example .env
# add your ANTHROPIC_API_KEY to .env

docker-compose up --build
# API at http://localhost:8000
```

## Running tests

```bash
pip install -r requirements.txt
pytest -v
# 27 tests, agent logic tested with mocked LLM calls — no API key needed to run the suite
```

## Example flow

```bash
# 1. Register and log in
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "sufyaan", "email": "you@example.com", "password": "Secure123!"}'

curl -X POST http://localhost:8000/auth/token \
  -d 'username=you@example.com&password=Secure123!'

# 2. Set your resume text (the agent compares every JD against this)
curl -X PUT http://localhost:8000/auth/me/resume \
  -H "Authorization: Bearer <token>" \
  -d '{"resume_text": "MSc Human-Centred AI... Python, Django, FastAPI, LangGraph..."}'

# 3. Add a company, then a job posting
curl -X POST http://localhost:8000/companies/ \
  -H "Authorization: Bearer <token>" \
  -d '{"name": "Acme Corp"}'

curl -X POST http://localhost:8000/job-postings/ \
  -H "Authorization: Bearer <token>" \
  -d '{"company_id": "<id>", "title": "Backend Engineer", "raw_description": "<paste JD>"}'

# 4. Trigger analysis, then poll for the result
curl -X POST http://localhost:8000/job-postings/<id>/analyze -H "Authorization: Bearer <token>"
curl http://localhost:8000/job-postings/<id>/analysis -H "Authorization: Bearer <token>"
```

## AWS roadmap (next phase)

Local Docker Compose is deliberately the first milestone, not the end state. Once deployed:

- **ECS Fargate** for the API and worker containers, behind an **ALB**
- **RDS PostgreSQL** replacing the containerised Postgres
- **SQS** replacing Redis/Celery as the broker (or ElastiCache Redis if keeping Celery)
- **Secrets Manager** for the Anthropic API key instead of a plain `.env`
- **EventBridge** to schedule a periodic sweep of `upcoming-follow-ups` and email a digest via **SES**
- **CloudWatch** for logs/metrics on task success rate and per-analysis latency

## Design decisions

- **No auto-scraping** — LinkedIn/Indeed ToS makes automated scraping legally murky. You paste the JD in; the agent does the analysis. Keeps the project honest about what it actually does.
- **Resume as free text, not structured fields** — lets you paste your actual resume rather than re-encoding it into a rigid schema, and the LLM handles unstructured-to-structured matching, which is exactly the kind of task LLMs are good at.
- **Portable UUID column type** (`app/db_types.py`) — native UUID on Postgres in production, `CHAR(36)` on SQLite in tests, so the full test suite runs without a real database.
