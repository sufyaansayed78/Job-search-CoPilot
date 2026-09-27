import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import "./Dashboard.css";

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

export function Dashboard() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.dashboardStats().then(setStats).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error-text">{error}</p>;
  if (!stats) return <p className="muted">Loading…</p>;

  const maxCount = Math.max(1, ...Object.values(stats.by_status));

  return (
    <div>
      <PageHeader title="Dashboard" />

      <div className="readout">
        <div className="readout__item">
          <span className="readout__num mono">{stats.total_applications}</span>
          <span className="readout__label">Total applications</span>
        </div>
        <div className="readout__item">
          <span className="readout__num mono">{stats.response_rate_pct}%</span>
          <span className="readout__label">Response rate</span>
        </div>
        <div className="readout__item">
          <span className="readout__num mono">
            {stats.avg_match_score_applied ?? "—"}
          </span>
          <span className="readout__label">Avg. match score (applied)</span>
        </div>
        <div className="readout__item">
          <span className="readout__num mono">{stats.upcoming_follow_ups}</span>
          <span className="readout__label">Upcoming follow-ups</span>
        </div>
      </div>

      <h2 style={{ margin: "32px 0 14px" }}>Status breakdown</h2>
      <div className="status-bars">
        {Object.entries(stats.by_status).map(([status, count]) => (
          <div className="status-bar-row" key={status}>
            <span className="status-bar-row__label">{STATUS_LABELS[status] || status}</span>
            <div className="status-bar-row__track">
              <div
                className="status-bar-row__fill"
                style={{ width: `${(count / maxCount) * 100}%` }}
              />
            </div>
            <span className="status-bar-row__count mono">{count}</span>
          </div>
        ))}
      </div>

      {stats.total_applications === 0 && (
        <p className="muted" style={{ marginTop: 20 }}>
          Nothing tracked yet. <Link to="/postings">Add a job posting</Link> to run your first fit analysis.
        </p>
      )}
    </div>
  );
}
