// SourceList.jsx - the document chunks the answer was based on.
// Uses <details> so sources are collapsed by default and need no extra JavaScript.

export default function SourceList({ sources, insufficient }) {
  if (!sources || !sources.length) return null;
  return (
    <details className="sources">
      <summary>
        {insufficient ? "Closest matches found" : "Sources"} ({sources.length})
      </summary>
      <ol>
        {sources.map((s) => (
          <li key={`${s.document_id}-${s.chunk_index}`}>
            <div className="source-head">
              <span className="cite">{s.ref}</span>
              <strong>{s.document_name}</strong>
              {s.page != null && <span className="muted small">page {s.page}</span>}
              <span className="muted small">chunk {s.chunk_index}</span>
              <span className="score" title="Similarity between the question and this chunk (0–1)">
                {Math.round(s.relevance_score * 100)}% match
              </span>
            </div>
            <p className="snippet">{s.snippet}</p>
          </li>
        ))}
      </ol>
    </details>
  );
}
