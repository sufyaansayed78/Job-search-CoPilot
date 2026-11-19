import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
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
  const [gmailConnecting, setGmailConnecting] = useState(false);
  const [gmailError, setGmailError] = useState("");
  const [syncStarting, setSyncStarting] = useState(false);
  const [activeSyncJobId, setActiveSyncJobId] = useState(null);
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncError, setSyncError] = useState("");
  const [searchParams] = useSearchParams();
  const gmailConnected = searchParams.get("gmail") === "connected";

  useEffect(() => {
    Promise.all([api.listApplications(), api.listPostings(), api.listCompanies()]).then(
      ([apps, posts, cos]) => {
        setApplications(apps);
        setPostings(Object.fromEntries(posts.map((p) => [p.id, p])));
        setCompanies(Object.fromEntries(cos.map((c) => [c.id, c])));
      }
    ).finally(() => setLoading(false));
  }, []);

  // Poll the backend while this sync job is queued or running.
  useEffect(() => {
    if (!activeSyncJobId) return undefined;

    let cancelled = false;
    let timeoutId;

    async function pollSyncStatus() {
      try {
        const status = await api.getGmailSyncStatus(activeSyncJobId);
        if (cancelled) return;

        setSyncStatus(status);
        const normalizedStatus = String(status.status || "").toLowerCase();
        const finishedStatuses = ["completed", "complete", "success", "succeeded", "failed", "error"];

        if (finishedStatuses.includes(normalizedStatus)) {
          setActiveSyncJobId(null);
          return;
        }

        timeoutId = window.setTimeout(pollSyncStatus, 2000);
      } catch (error) {
        if (cancelled) return;
        setSyncError(error.message || "Could not retrieve Gmail sync status.");
        setActiveSyncJobId(null);
      }
    }

    pollSyncStatus();
    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [activeSyncJobId]);

  async function handleConnectGmail() {
    setGmailConnecting(true);
    setGmailError("");

    try {
      // FastAPI returns the Google authorization URL. We then navigate the
      // browser to Google so the user can approve Gmail access.
      const response = await api.connectGmail();
      if (!response?.authorization_url) {
        throw new Error("The server did not return a Google authorization URL.");
      }
      window.location.assign(response.authorization_url);
    } catch (error) {
      setGmailError(error.message || "Could not start Gmail connection.");
      setGmailConnecting(false);
    }
  }

  async function handleStartGmailSync() {
    setSyncStarting(true);
    setSyncError("");
    setSyncStatus(null);

    try {
      const response = await api.startGmailSync();
      if (!response?.job_id) {
        throw new Error("The server did not return a Gmail sync job ID.");
      }
      setActiveSyncJobId(response.job_id);
      setSyncStatus({ status: "queued", emails_checked: 0, updates_applied: 0, suggestions_created: 0 });
    } catch (error) {
      setSyncError(error.message || "Could not start Gmail synchronisation.");
    } finally {
      setSyncStarting(false);
    }
  }

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
      <PageHeader
        title="Applications"
        action={
          <div className="gmail-actions">
            <button
              type="button"
              className="btn btn-quiet"
              onClick={handleConnectGmail}
              disabled={gmailConnecting}
            >
              {gmailConnecting ? "Connecting…" : "Connect Gmail"}
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleStartGmailSync}
              disabled={syncStarting || Boolean(activeSyncJobId)}
            >
              {syncStarting || activeSyncJobId ? "Syncing…" : "Sync Gmail"}
            </button>
          </div>
        }
      />

      {gmailConnected && (
        <div className="gmail-notice gmail-notice--success" role="status">
          Gmail connected successfully. Your account is ready to sync emails.
        </div>
      )}
      {gmailError && (
        <div className="gmail-notice gmail-notice--error" role="alert">
          {gmailError}
        </div>
      )}
      {syncError && (
        <div className="gmail-notice gmail-notice--error" role="alert">
          {syncError}
        </div>
      )}
      {syncStatus && (
        <section className="gmail-sync-panel" aria-live="polite">
          <div className="gmail-sync-panel__heading">
            <strong>Gmail sync: {String(syncStatus.status || "unknown").replaceAll("_", " ")}</strong>
            {activeSyncJobId && <span className="muted">Checking for updates…</span>}
          </div>
          <div className="gmail-sync-stats">
            <span><strong>{syncStatus.emails_checked ?? 0}</strong> emails checked</span>
            <span><strong>{syncStatus.updates_applied ?? 0}</strong> updates applied</span>
            <span><strong>{syncStatus.suggestions_created ?? 0}</strong> suggestions created</span>
          </div>
          {syncStatus.error && (
            <p className="gmail-sync-panel__error">{syncStatus.error}</p>
          )}
        </section>
      )}

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
