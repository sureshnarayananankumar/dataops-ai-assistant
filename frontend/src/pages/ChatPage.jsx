// ChatPage.jsx - the dashboard. It owns the app's state (documents, messages,
// loading flags) and passes data + callback functions down to components.
//
//   ChatPage
//   ├── Sidebar      (upload button, document list, backend status)
//   └── main
//       ├── ChatWindow   (MessageBubble -> SourceList, LoadingIndicator)
//       └── ChatInput
import { useCallback, useEffect, useState } from "react";
import Sidebar from "../components/Sidebar.jsx";
import ChatWindow from "../components/ChatWindow.jsx";
import ChatInput from "../components/ChatInput.jsx";
import { askQuestion, deleteDocument, getHealth, listDocuments, uploadDocument } from "../services/api.js";

export default function ChatPage() {
  const [documents, setDocuments] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]); // empty = search all documents
  const [messages, setMessages] = useState([]);
  const [health, setHealth] = useState(null);
  const [isAsking, setIsAsking] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [notice, setNotice] = useState(null); // { type: "error" | "success", text }
  const [sidebarOpen, setSidebarOpen] = useState(false); // used on small screens

  const refreshDocuments = useCallback(async () => {
    try {
      setDocuments(await listDocuments());
    } catch (err) {
      setNotice({ type: "error", text: err.message });
    }
  }, []);

  // On first load: check the backend and fetch the document list.
  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth({ status: "down" }));
    refreshDocuments();
  }, [refreshDocuments]);

  async function handleUpload(files) {
    setIsUploading(true);
    setNotice(null);
    for (const file of files) {
      try {
        const result = await uploadDocument(file);
        setNotice({ type: "success", text: result.message });
      } catch (err) {
        setNotice({ type: "error", text: `${file.name}: ${err.message}` });
      }
    }
    setIsUploading(false);
    refreshDocuments();
  }

  async function handleDelete(doc) {
    if (!window.confirm(`Delete "${doc.filename}"?`)) return;
    try {
      await deleteDocument(doc.id);
      setSelectedIds((ids) => ids.filter((id) => id !== doc.id));
      refreshDocuments();
    } catch (err) {
      setNotice({ type: "error", text: err.message });
    }
  }

  function toggleSelected(id) {
    setSelectedIds((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]));
  }

  async function handleAsk(question) {
    setMessages((m) => [...m, { role: "user", text: question }]);
    setIsAsking(true);
    try {
      const res = await askQuestion(question, selectedIds);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: res.answer,
          sources: res.sources,
          insufficient: res.insufficient_information,
          evaluation: res.evaluation,
          attempts: res.attempts,
        },
      ]);
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", text: err.message, isError: true }]);
    } finally {
      setIsAsking(false);
    }
  }

  const scopeLabel = selectedIds.length
    ? `Searching ${selectedIds.length} selected document${selectedIds.length > 1 ? "s" : ""}`
    : `Searching all ${documents.length} document${documents.length === 1 ? "" : "s"}`;

  return (
    <div className="layout">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        documents={documents}
        selectedIds={selectedIds}
        onToggle={toggleSelected}
        onDelete={handleDelete}
        onUpload={handleUpload}
        isUploading={isUploading}
        health={health}
      />

      <main className="main">
        <header className="topbar">
          <button className="icon-button menu-button" onClick={() => setSidebarOpen(true)} aria-label="Open documents">
            ☰
          </button>
          <div>
            <h1>DataOps AI Assistant</h1>
            <p className="muted">{scopeLabel}</p>
          </div>
          <button className="button secondary" onClick={() => setMessages([])} disabled={!messages.length || isAsking}>
            Clear chat
          </button>
        </header>

        {notice && (
          <div className={`notice ${notice.type}`} role="status">
            <span>{notice.text}</span>
            <button className="icon-button" onClick={() => setNotice(null)} aria-label="Dismiss">
              ×
            </button>
          </div>
        )}

        <ChatWindow messages={messages} isLoading={isAsking} onExample={handleAsk} hasDocuments={documents.length > 0} />
        <ChatInput onSend={handleAsk} disabled={isAsking} />
      </main>
    </div>
  );
}
