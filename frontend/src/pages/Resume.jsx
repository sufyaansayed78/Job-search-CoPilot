import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { api } from "../api/client";
import { PageHeader } from "../components/PageHeader";

export function Resume() {
  const { user, refreshUser } = useAuth();
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (user) setText(user.resume_text || "");
  }, [user]);

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    try {
      await api.updateResume(text);
      await refreshUser();
      setSaved(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <PageHeader title="Resume" />
      <p className="muted" style={{ marginBottom: 16, maxWidth: 560 }}>
        This is what every job posting gets compared against. Paste your actual resume text or a
        skills summary — the more specific, the more accurate the fit scores will be.
      </p>
      <form onSubmit={handleSave}>
        <div className="field">
          <textarea
            value={text}
            onChange={(e) => { setText(e.target.value); setSaved(false); }}
            rows={16}
            placeholder="Paste your resume or a skills summary here…"
            style={{ maxWidth: 640 }}
          />
        </div>
        <button className="btn btn-primary" type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save resume"}
        </button>
        {saved && <span className="muted" style={{ marginLeft: 12, fontSize: 13 }}>Saved.</span>}
      </form>
    </div>
  );
}
