// ChatWindow.jsx - scrollable list of messages, the loading indicator,
// and a welcome screen with example questions when the chat is empty.
import { useEffect, useRef } from "react";
import MessageBubble from "./MessageBubble.jsx";
import LoadingIndicator from "./LoadingIndicator.jsx";

const EXAMPLES = [
  "What is a DBT incremental model?",
  "How can I troubleshoot a failed data pipeline?",
  "Explain Snowflake Streams and Tasks.",
  "What is the purpose of a staging layer?",
  "Summarize the uploaded document.",
];

export default function ChatWindow({ messages, isLoading, onExample, hasDocuments }) {
  const bottomRef = useRef(null);

  // Scroll to the newest message whenever messages change.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (!messages.length && !isLoading) {
    return (
      <section className="chat-window welcome">
        <h2>Ask questions about your documentation</h2>
        <p className="muted">
          {hasDocuments
            ? "Answers come only from your uploaded documents, with sources."
            : "Start by uploading a document from the sidebar (try the files in sample_documents/)."}
        </p>
        <div className="examples">
          {EXAMPLES.map((q) => (
            <button key={q} className="example" onClick={() => onExample(q)} disabled={!hasDocuments}>
              {q}
            </button>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="chat-window" aria-live="polite">
      {messages.map((message, i) => (
        <MessageBubble key={i} message={message} />
      ))}
      {isLoading && <LoadingIndicator />}
      <div ref={bottomRef} />
    </section>
  );
}
