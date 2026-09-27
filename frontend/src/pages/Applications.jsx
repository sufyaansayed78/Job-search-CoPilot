import { useEffect, useState } from "react";
import { api } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import "./Applications.css";

const STATUSES = [
  "wishlist", "applied", "phone_screen", "technical", "onsite", "offer", "rejected", "withdrawn",
];
const STATUS_LABELS = {
  wishlist: "Wishlist",
  applied: "Applied",
  phone_screen: "Phone screen",
  technical: "Technical",
  onsite: "Onsite",
  offer: "Offer",
  rejected: "Rejected",
  withdrawn: "Withdrawn",
};

export function Applications() {
  const [applications, setApplications] = useState([]);
  const [postings, setPostings] = useState({});
  const [companies, setCompanies] = useState({});
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState(null);

  useEffect(() => {
    Promise.all([api.listApplications(), api.listPostings(), api.listCompanies()]).then(
      ([apps, posts, cos]) => {
        setApplications(apps);
        setPostings(Object.fromEntries(posts.map((p) => [p.id, p])));
        setCompanies(Object.fromEntries(cos.map((c) => [c.id, c])));
      }
    ).finally(() => setLoading(false));
  }, []);

  async function handleStatusChange(id, status) {
    setSavingId(id);
    try {
      const updated = await api.updateApplicationStatus(id, { status });
      setApplications((all) => all.map((a) => (a.id === id ? updated : a)));
    } finally {
      setSavingId(null);
    }
  }

  function postingTitle(id) {
    const posting = postings[id];
    if (!posting) return "—";
    const company = companies[posting.company_id];
    return `${posting.title} · ${company ? company.name : "Unknown"}`;
  }

  return (
    <div>
      <PageHeader title="Applications" />

      {loading && <p className="muted">Loading…</p>}
      {!loading && applications.length === 0 && (
        <p className="muted">Nothing tracked yet — track an application from a job posting's analysis.</p>
      )}

      <ul className="app-list">
        {applications.map((a) => (
          <li className="app-row" key={a.id}>
            <div className="app-row__main">
              <div className="app-row__title">{postingTitle(a.job_posting_id)}</div>
              {a.follow_up_date && (
                <div className="app-row__followup muted">
                  Follow up {new Date(a.follow_up_date).toLocaleDateString()}
                </div>
              )}
            </div>
            <select
              value={a.status}
              disabled={savingId === a.id}
              onChange={(e) => handleStatusChange(a.id, e.target.value)}
              className={`status-select status-select--${a.status}`}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>{STATUS_LABELS[s]}</option>
              ))}
            </select>
          </li>
        ))}
      </ul>
    </div>
  );
}
