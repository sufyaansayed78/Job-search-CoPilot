import { useEffect, useState } from "react";
import { api } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { Modal } from "../components/Modal";
import "./ListPages.css";

export function Companies() {
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: "", website: "", notes: "" });
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function refresh() {
    return api.listCompanies().then(setCompanies).finally(() => setLoading(false));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleAdd(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.createCompany(form);
      setForm({ name: "", website: "", notes: "" });
      setShowAdd(false);
      await refresh();
    } catch (err) {
      setError(err.detail || "Couldn't add that company.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Companies"
        action={<button className="btn btn-primary" onClick={() => setShowAdd(true)}>Add company</button>}
      />

      {loading && <p className="muted">Loading…</p>}

      {!loading && companies.length === 0 && (
        <p className="muted">No companies yet. Add one to start logging job postings against it.</p>
      )}

      <ul className="simple-list">
        {companies.map((c) => (
          <li className="simple-list__row" key={c.id}>
            <div>
              <div className="simple-list__title">{c.name}</div>
              {c.website && (
                <a href={c.website} target="_blank" rel="noreferrer" className="simple-list__meta">
                  {c.website}
                </a>
              )}
            </div>
            {c.notes && <div className="simple-list__notes muted">{c.notes}</div>}
          </li>
        ))}
      </ul>

      {showAdd && (
        <Modal title="Add company" onClose={() => setShowAdd(false)}>
          <form onSubmit={handleAdd}>
            <div className="field">
              <label htmlFor="c-name">Name</label>
              <input id="c-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </div>
            <div className="field">
              <label htmlFor="c-website">Website</label>
              <input id="c-website" value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} placeholder="https://" />
            </div>
            <div className="field">
              <label htmlFor="c-notes">Notes</label>
              <input id="c-notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="How you found them, a contact, etc." />
            </div>
            {error && <p className="error-text">{error}</p>}
            <button className="btn btn-primary" type="submit" disabled={saving}>
              {saving ? "Adding…" : "Add company"}
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}
