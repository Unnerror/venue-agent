"use client";
import { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "bot";
  text: string;
}

const SUGGESTIONS = [
  "What's on this weekend?",
  "Tell me about upcoming concerts",
  "How do I get tickets?",
  "Is there parking nearby?",
];

function formatText(text: string) {
  return text
    // Bold **text**
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    // Markdown links [text](url)
    .replace(
      /\[([^\]]+)\]\((https?:\/\/[^\)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    )
    // Line breaks
    .replace(/\n/g, "<br/>");
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "bot",
      text: "Welcome to Théâtre Rialto. Ask me about upcoming events, tickets, accessibility, or anything else about the venue.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async (question: string) => {
    if (!question.trim() || loading) return;
    const q = question.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: data.answer || data.error || "Something went wrong." },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: "Could not reach the server. Please try again." },
      ]);
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  };

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  };

  const showSuggestions = messages.length === 1 && !loading;

  return (
    <>
      <div className="curtain-left" />
      <div className="curtain-right" />
      <div className="container">
        <header className="header">
          <p className="header-eyebrow">Est. 1923 · Montréal</p>
          <h1>Théâtre <em>Rialto</em></h1>
          <p className="header-sub">Your concierge for events & venue information</p>
          <div className="divider" style={{ marginTop: 16, marginBottom: 0 }} />
        </header>

        <div className="messages">
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <span className="role-label">
                {msg.role === "user" ? "You" : "Rialto"}
              </span>
              <div
                className="bubble"
                dangerouslySetInnerHTML={{ __html: formatText(msg.text) }}
              />
            </div>
          ))}

          {loading && (
            <div className="message bot">
              <span className="role-label">Rialto</span>
              <div className="typing">
                <span /><span /><span />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="input-area">
          {showSuggestions && (
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="suggestion" onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}
          <div className="input-row">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInput}
              onKeyDown={handleKey}
              placeholder="Ask about events, tickets, accessibility…"
              rows={1}
              disabled={loading}
            />
            <button
              className="send-btn"
              onClick={() => send(input)}
              disabled={!input.trim() || loading}
              aria-label="Send"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M2 8L14 2L8 14L7 9L2 8Z" fill="currentColor" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
