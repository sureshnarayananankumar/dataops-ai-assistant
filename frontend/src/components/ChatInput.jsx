// ChatInput.jsx - the question box. Enter sends, Shift+Enter adds a new line.
import { useState } from "react";

export default function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState("");

  function send() {
    const question = text.trim();
    if (!question || disabled) return;
    onSend(question);
    setText("");
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  }

  return (
    <div className="chat-input">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question about your documents…"
        rows={1}
        maxLength={2000}
        aria-label="Question"
      />
      <button className="button primary" onClick={send} disabled={disabled || !text.trim()}>
        Send
      </button>
    </div>
  );
}
