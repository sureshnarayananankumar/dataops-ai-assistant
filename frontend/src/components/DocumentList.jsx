// DocumentList.jsx - list of uploaded documents with select checkboxes and delete.

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function DocumentList({ documents, selectedIds, onToggle, onDelete }) {
  if (!documents.length) {
    return <p className="empty-docs muted small">No documents yet. Upload one to get started.</p>;
  }
  return (
    <ul className="doc-list">
      {documents.map((doc) => (
        <li key={doc.id} className={`doc-item ${selectedIds.includes(doc.id) ? "selected" : ""}`}>
          <label>
            <input type="checkbox" checked={selectedIds.includes(doc.id)} onChange={() => onToggle(doc.id)} />
            <span className="doc-badge">{doc.file_type}</span>
            <span className="doc-text">
              <span className="doc-name" title={doc.filename}>
                {doc.filename}
              </span>
              <span className="muted small">
                {doc.num_chunks} chunks · {formatSize(doc.size_bytes)}
              </span>
            </span>
          </label>
          <button className="icon-button delete" onClick={() => onDelete(doc)} aria-label={`Delete ${doc.filename}`}>
            🗑
          </button>
        </li>
      ))}
    </ul>
  );
}
