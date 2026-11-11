// api.js - the ONLY file that talks to the FastAPI backend.
//
// React components call these functions; each one sends an HTTP request with
// fetch() and returns the parsed JSON. If the backend URL or an endpoint
// changes, only this file needs to change.

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, options);
  } catch {
    throw new Error(`Cannot reach the backend at ${API_URL}. Is it running?`);
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    // FastAPI puts error messages in "detail" (a string, or a list for validation errors)
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(", ") : data.detail;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return data;
}

export function getHealth() {
  return request("/health");
}

export function listDocuments() {
  return request("/documents");
}

export function uploadDocument(file) {
  // Files are sent as multipart/form-data; the browser sets the header itself.
  const form = new FormData();
  form.append("file", file);
  return request("/upload", { method: "POST", body: form });
}

export function deleteDocument(documentId) {
  return request(`/documents/${documentId}`, { method: "DELETE" });
}

export function askQuestion(question, documentIds = []) {
  return request("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, document_ids: documentIds.length ? documentIds : null }),
  });
}
