// MessageBubble.jsx - one chat message. AI messages also show an evaluation
// badge and the source references used to build the answer.
import SourceList from "./SourceList.jsx";

// Render **bold**, `code` and [1] citations without using innerHTML (safer).
function renderInline(text, keyPrefix) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[\d+\])/g);
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={key}>{part.slice(2, -2)}</strong>;
    if (/^`[^`]+`$/.test(part)) return <code key={key}>{part.slice(1, -1)}</code>;
    if (/^\[\d+\]$/.test(part)) return <sup key={key} className="cite">{part.slice(1, -1)}</sup>;
    return part;
  });
}

// Very small formatter: code blocks, bullet lists and paragraphs.
function FormattedText({ text }) {
  const blocks = [];
  const lines = text.split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim().startsWith("```")) {
      const code = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) code.push(lines[i++]);
      i++;
      blocks.push(<pre key={blocks.length}><code>{code.join("\n")}</code></pre>);
    } else if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\s*([-*]|\d+\.)\s+/, ""));
        i++;
      }
      blocks.push(
        <ul key={blocks.length}>
          {items.map((item, j) => <li key={j}>{renderInline(item, `${blocks.length}-${j}`)}</li>)}
        </ul>
      );
    } else if (line.trim()) {
      blocks.push(<p key={blocks.length}>{renderInline(line.replace(/^#+\s*/, ""), blocks.length)}</p>);
      i++;
    } else {
      i++;
    }
  }
  return <>{blocks}</>;
}

function EvaluationBadge({ message }) {
  const ev = message.evaluation;
  if (message.insufficient) return <span className="badge warn">Not enough information in documents</span>;
  if (!ev) return null;
  const label = ev.passed ? "Grounded in sources" : "Not verified";
  return (
    <span
      className={`badge ${ev.passed ? "ok" : "warn"}`}
      title={`Groundedness ${ev.groundedness_score} · retrieval relevance ${ev.retrieval_relevance} · ${ev.reason}`}
    >
      {label}
      {message.attempts > 1 ? " · after retry" : ""}
    </span>
  );
}

export default function MessageBubble({ message }) {
  const isUser = message.role === "user";
  return (
    <div className={`message ${isUser ? "user" : "assistant"} ${message.isError ? "error" : ""}`}>
      <div className="avatar">{isUser ? "You" : "AI"}</div>
      <div className="bubble">
        {isUser ? <p>{message.text}</p> : <FormattedText text={message.text} />}
        {!isUser && !message.isError && (
          <>
            <EvaluationBadge message={message} />
            <SourceList sources={message.sources} insufficient={message.insufficient} />
          </>
        )}
      </div>
    </div>
  );
}
