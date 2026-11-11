// LoadingIndicator.jsx - shown while the agent is working on an answer.

export default function LoadingIndicator() {
  return (
    <div className="message assistant">
      <div className="avatar">AI</div>
      <div className="bubble loading">
        <span className="dots" aria-hidden="true">
          <span />
          <span />
          <span />
        </span>
        <span className="muted small">Understanding question → retrieving → answering → checking sources…</span>
      </div>
    </div>
  );
}
