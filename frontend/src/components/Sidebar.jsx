// Sidebar.jsx - left panel: upload button, uploaded documents, backend status.
import UploadButton from "./UploadButton.jsx";
import DocumentList from "./DocumentList.jsx";

function StatusLine({ health }) {
  if (!health) return <p className="status muted">Checking backend…</p>;
  if (health.status !== "ok") return <p className="status error-text">● Backend offline</p>;
  if (!health.api_key_configured)
    return <p className="status warn-text">● API key missing in .env ({health.llm_provider})</p>;
  return (
    <p className="status ok-text" title={`Embeddings: ${health.embedding_model}`}>
      ● Connected · {health.llm_provider} / {health.chat_model}
    </p>
  );
}

export default function Sidebar({ open, onClose, documents, selectedIds, onToggle, onDelete, onUpload, isUploading, health }) {
  return (
    <>
      {open && <div className="backdrop" onClick={onClose} />}
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand">
          <div className="logo">D</div>
          <div>
            <strong>DataOps AI</strong>
            <span className="muted small">Agentic RAG assistant</span>
          </div>
          <button className="icon-button close-button" onClick={onClose} aria-label="Close documents">
            ×
          </button>
        </div>

        <UploadButton onUpload={onUpload} isUploading={isUploading} />

        <div className="section-title">
          <span>Documents</span>
          <span className="count">{documents.length}</span>
        </div>
        <p className="muted small hint">Tick documents to limit the search. None ticked = all.</p>
        <DocumentList documents={documents} selectedIds={selectedIds} onToggle={onToggle} onDelete={onDelete} />

        <StatusLine health={health} />
      </aside>
    </>
  );
}
