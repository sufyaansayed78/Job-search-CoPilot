import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { Modal } from "../components/Modal";
import { FitScore, VerdictBar } from "../components/FitScore";
import "./JobPostings.css";

const POLL_MS = 2500;

export function JobPostings() {
  const [postings, setPostings] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [analyses, setAnalyses] = useState({}); // posting id -> GapAnalysisOut
  const [expandedId, setExpandedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ company_id: "", title: "", url: "", source: "manual", raw_description: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [trackedIds, setTrackedIds] = useState(new Set());
  const pollRef = useRef(null);

  function refresh() {
    return Promise.all([api.listPostings(), api.listCompanies()]).then(([p, c]) => {
      setPostings(p);
      setCompanies(c);
      if (c.length && !form.company_id) setForm((f) => ({ ...f, company_id: c[0].id }));
    }).finally(() => setLoading(false));
  }

  useEffect(() => {
    refresh();
  }, []);

  // Poll for any posting whose analysis is still running. One shared
  // interval rather than one per row, so N pending postings cost one
  // timer, not N.
  useEffect(() => {
    pollRef.current = setInterval(async () => {
      const pending = postings.filter((p) => p.analysis_status === "pending");
      for (const posting of pending) {
        try {
          const result = await api.getAnalysis(posting.id);
          if (!result.pending) {
            setAnalyses((a) => ({ ...a, [posting.id]: result }));
            setPostings((all) =>
              all.map((p) => (p.id === posting.id ? { ...p, analysis_status: "done" } : p))
            );
          }
        } catch {
          setPostings((all) =>
            all.map((p) => (p.id === posting.id ? { ...p, analysis_status: "failed" } : p))
          );
        }
      }
    }, POLL_MS);
    return () => clearInterval(pollRef.current);
  }, [postings]);

  async function handleAdd(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.createPosting(form);
      setForm((f) => ({ ...f, title: "", url: "", raw_description: "" }));
      setShowAdd(false);
      await refresh();
    } catch (err) {
      setError(err.detail || "Couldn't add that posting.");
    } finally {
      setSaving(false);
    }
  }

  async function handleAnalyze(id) {
    setPostings((all) => all.map((p) => (p.id === id ? { ...p, analysis_status: "pending" } : p)));
    try {
      await api.analyzePosting(id);
    } catch {
      setPostings((all) => all.map((p) => (p.id === id ? { ...p, analysis_status: "failed" } : p)));
    }
  }

  async function handleTrack(id) {
    try {
      await api.createApplication({ job_posting_id: id });
      setTrackedIds((s) => new Set(s).add(id));
    } catch {
      // Already tracked or transient error — the button already shows
      // "Tracked" optimistically-adjacent state via trackedIds, so a
      // quiet failure here isn't left unexplained to the user.
    }
  }

  function companyName(id) {
    return companies.find((c) => c.id === id)?.name || "Unknown company";
  }

  return (
    <div>
      <PageHeader
        title="Job postings"
        action={
          <button className="btn btn-primary" onClick={() => setShowAdd(true)} disabled={companies.length === 0}>
            Add posting
          </button>
        }
      />

      {!loading && companies.length === 0 && (
        <p className="muted">Add a company first, then you can log a job posting against it.</p>
      )}

      {loading && <p className="muted">Loading…</p>}

      <ul className="posting-list">
        {postings.map((p) => {
          const isOpen = expandedId === p.id;
          const analysis = analyses[p.id];
          return (
            <li className="posting-row" key={p.id}>
              <button className="posting-row__main" onClick={() => setExpandedId(isOpen ? null : p.id)}>
                <VerdictBar status={p.analysis_status} recommendation={analysis?.recommendation} />
                <div className="posting-row__info">
                  <div className="posting-row__title">{p.title}</div>
                  <div className="posting-row__company muted">{companyName(p.company_id)}</div>
                </div>
                <FitScore status={p.analysis_status} score={analysis?.match_score} recommendation={analysis?.recommendation} size="sm" />
              </button>

              {isOpen && (
                <div className="posting-row__detail">
                  {p.analysis_status === "not_started" && (
                    <button className="btn btn-primary" onClick={() => handleAnalyze(p.id)}>
                      Run analysis
                    </button>
                  )}
                  {p.analysis_status === "pending" && (
                    <p className="muted pulse">Comparing this against your resume…</p>
                  )}
                  {p.analysis_status === "failed" && (
                    <div>
                      <p className="error-text">Analysis failed — check your Anthropic API key is set, then retry.</p>
                      <button className="btn btn-quiet" onClick={() => handleAnalyze(p.id)}>Retry</button>
                    </div>
                  )}
                  {p.analysis_status === "done" && analysis && (
                    <div className="analysis">
                      <p>{analysis.summary}</p>
                      <div className="skill-groups">
                        <div>
                          <h3>Matched</h3>
                          <div className="chips">
                            {analysis.matched_skills.map((s) => (
                              <span className="chip chip--matched" key={s}>{s}</span>
                            ))}
                            {analysis.matched_skills.length === 0 && <span className="muted">None</span>}
                          </div>
                        </div>
                        <div>
                          <h3>Missing</h3>
                          <div className="chips">
                            {analysis.missing_skills.map((s) => (
                              <span className="chip chip--missing" key={s}>{s}</span>
                            ))}
                            {analysis.missing_skills.length === 0 && <span className="muted">None</span>}
                          </div>
                        </div>
                      </div>
                      <button
                        className="btn btn-primary"
                        onClick={() => handleTrack(p.id)}
                        disabled={trackedIds.has(p.id)}
                        style={{ marginTop: 14 }}
                      >
                        {trackedIds.has(p.id) ? "Tracked" : "Track this application"}
                      </button>
                    </div>
                  )}

                  <details className="posting-row__jd">
                    <summary>View job description</summary>
                    <pre>{p.raw_description}</pre>
                  </details>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {!loading && postings.length === 0 && companies.length > 0 && (
        <p className="muted">No postings yet. Paste one in to get your first fit score.</p>
      )}

      {showAdd && (
        <Modal title="Add job posting" onClose={() => setShowAdd(false)}>
          <form onSubmit={handleAdd}>
            <div className="field">
              <label htmlFor="p-company">Company</label>
              <select id="p-company" value={form.company_id} onChange={(e) => setForm({ ...form, company_id: e.target.value })} required>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="p-title">Job title</label>
              <input id="p-title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required />
            </div>
            <div className="field">
              <label htmlFor="p-url">Posting URL</label>
              <input id="p-url" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="https://" />
            </div>
            <div className="field">
              <label htmlFor="p-desc">Job description</label>
              <textarea id="p-desc" value={form.raw_description} onChange={(e) => setForm({ ...form, raw_description: e.target.value })} rows={8} required />
            </div>
            {error && <p className="error-text">{error}</p>}
            <button className="btn btn-primary" type="submit" disabled={saving}>
              {saving ? "Adding…" : "Add posting"}
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}
