import { FormEvent, useMemo, useState } from "react";

type Citation = { path: string; drive_file_id: string };

type ChatApiResponse = {
  answer: string;
  citations: Citation[];
  confidence: string;
  best_score: number;
};

type ChatMessage =
  | { role: "user"; text: string }
  | { role: "assistant"; payload: ChatApiResponse };

export default function App() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasThread = useMemo(() => messages.length > 0, [messages.length]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    setError(null);
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setLoading(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `Request failed (${res.status})`);
      }
      const data = (await res.json()) as ChatApiResponse;
      setMessages((m) => [...m, { role: "assistant", payload: data }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <h1>HR Assistant</h1>
      <p className="sub">
        Answers come from your indexed Google Drive HR library. Each reply includes document paths
        when the model had enough context; low-confidence topics are blocked from guessing.
      </p>

      <div className="chat">
        {!hasThread && (
          <div className="msg bot">
            Ask about policies, benefits, remote work, insurance, or other topics covered in your
            Drive folders. Example: &ldquo;What is the remote work policy for international
            travel?&rdquo;
          </div>
        )}
        {messages.map((msg, i) =>
          msg.role === "user" ? (
            <div key={i} className="msg user">
              {msg.text}
            </div>
          ) : (
            <div key={i} className="msg bot">
              {msg.payload.answer}
              <div className="msg-meta">
                <span
                  className={`badge ${msg.payload.confidence === "high" ? "high" : msg.payload.confidence === "medium" ? "medium" : "low"}`}
                >
                  Confidence: {msg.payload.confidence}
                </span>
                <span className="badge">Best match score: {msg.payload.best_score.toFixed(3)}</span>
              </div>
              {msg.payload.citations.length > 0 && (
                <div className="citations">
                  <strong>Sources (Drive paths)</strong>
                  <ul>
                    {msg.payload.citations.map((c) => (
                      <li key={c.path}>{c.path}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )
        )}
        {loading && <div className="msg bot">Searching documents and drafting an answer…</div>}
      </div>

      {error && <p className="err">{error}</p>}

      <form className="composer" onSubmit={onSubmit}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your HR question…"
          rows={2}
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </>
  );
}
