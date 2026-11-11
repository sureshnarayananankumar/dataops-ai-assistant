// UploadButton.jsx - a styled button that opens the file picker.
// The real <input type="file"> is hidden; clicking the button clicks it.
import { useRef } from "react";

export default function UploadButton({ onUpload, isUploading }) {
  const inputRef = useRef(null);

  function handleChange(event) {
    const files = Array.from(event.target.files || []);
    if (files.length) onUpload(files);
    event.target.value = ""; // allow uploading the same file again
  }

  return (
    <>
      <button className="button primary full" onClick={() => inputRef.current.click()} disabled={isUploading}>
        {isUploading ? "Processing…" : "+ Upload documents"}
      </button>
      <p className="muted small hint">PDF, TXT, Markdown or SQL · max 20 MB</p>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,.md,.sql"
        multiple
        hidden
        onChange={handleChange}
      />
    </>
  );
}
