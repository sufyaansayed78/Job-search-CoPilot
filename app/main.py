from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import auth, companies, job_postings, applications, dashboard, OAuth , Services

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Job Search Copilot",
    description="Tracks applications and runs an LLM agent that scores each "
                 "job description against your resume before you apply.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(job_postings.router)
app.include_router(applications.router)
app.include_router(dashboard.router)
app.include_router(OAuth.router)
app.include_router(Services.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "job-search-copilot"}
