const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function getToken() {
  return localStorage.getItem("jsc_token");
}

export function setToken(token) {
  if (token) localStorage.setItem("jsc_token", token);
  else localStorage.removeItem("jsc_token");
}

async function request(path, { method = "GET", body, form, auth = true } = {}) {
  const headers = {};
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let payload;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = new URLSearchParams(form).toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(`${API_URL}${path}`, { method, headers, body: payload });

  // 202 means "accepted, not ready yet" — the agent poll relies on this
  // being distinguishable from a hard failure, so it's returned, not thrown.
  if (res.status === 202) {
    const data = await res.json().catch(() => ({}));
    return { pending: true, ...data };
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(data.detail || `Request failed (${res.status})`, res.status, data.detail);
  }

  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  register: (payload) => request("/auth/register", { method: "POST", body: payload, auth: false }),
  login: (email, password) =>
    request("/auth/token", { method: "POST", form: { username: email, password }, auth: false }),
  me: () => request("/auth/me"),
  updateResume: (resume_text) => request("/auth/me/resume", { method: "PUT", body: { resume_text } }),

  listCompanies: () => request("/companies/"),
  createCompany: (payload) => request("/companies/", { method: "POST", body: payload }),

  listPostings: () => request("/job-postings/"),
  createPosting: (payload) => request("/job-postings/", { method: "POST", body: payload }),
  analyzePosting: (id) => request(`/job-postings/${id}/analyze`, { method: "POST" }),
  getAnalysis: (id) => request(`/job-postings/${id}/analysis`),

  listApplications: () => request("/applications/"),
  createApplication: (payload) => request("/applications/", { method: "POST", body: payload }),
  updateApplicationStatus: (id, payload) =>
    request(`/applications/${id}/status`, { method: "PATCH", body: payload }),
  upcomingFollowUps: () => request("/applications/upcoming-follow-ups"),

  dashboardStats: () => request("/dashboard/stats"),
};

export { ApiError };
