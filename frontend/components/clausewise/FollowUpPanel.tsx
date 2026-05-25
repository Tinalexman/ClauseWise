"use client";

import { useState, useRef, useEffect } from "react";
import Icon from "./Icon";
import { C } from "@/lib/tokens";
import { api } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  ts: number;
}

interface Props {
  clauseId: string | null;
  clauseText?: string;
}

const SUGGESTED = [
  "What are my obligations here?",
  "Can I cancel anytime?",
  "What is the realistic worst case?",
  "Is this clause standard for the industry?",
];

export default function FollowUpPanel({ clauseId, clauseText }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    setMessages([]);
    setInput("");
    setError(null);
  }, [clauseId]);

  async function submit(question: string) {
    if (!question.trim() || !clauseId || loading) return;
    const q = question.trim();
    setInput("");
    setError(null);
    const userMsg: Message = { role: "user", content: q, ts: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);
    try {
      const history = messages.map(m => ({ role: m.role, content: m.content }));
      const res = await api.followup({ clause_id: clauseId, question: q, conversation_history: history });
      setMessages(prev => [...prev, { role: "assistant", content: res.answer, ts: Date.now() }]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setMessages(prev => prev.slice(0, -1));
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  if (!clauseId) {
    return (
      <div style={{
        flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
        justifyContent: "center", height: "100%", padding: 32, textAlign: "center", gap: 14,
      }}>
        <div style={{
          width: 56, height: 56, borderRadius: 16, background: C.surface2,
          border: `1px solid ${C.border}`, display: "flex",
          alignItems: "center", justifyContent: "center",
        }}>
          <Icon name="msg" size={22} color={C.text3} />
        </div>
        <p style={{ fontSize: 13, color: C.text2, lineHeight: 1.6 }}>
          Select and analyze a clause first, then ask questions.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Messages */}
      <div style={{
        flex: 1, overflowY: "auto", padding: "20px 28px",
        display: "flex", flexDirection: "column", gap: 14,
      }}>
        {messages.length === 0 && !loading && (
          <>
            <div style={{
              background: C.surface, border: `1px solid ${C.border}`,
              borderRadius: 12, padding: "16px 18px",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                <Icon name="msg" size={14} color={C.sage} />
                <span style={{ fontSize: 12.5, fontWeight: 600, color: C.text }}>
                  Ask anything about this clause
                </span>
              </div>
              <p style={{ fontSize: 12.5, color: C.text2, lineHeight: 1.6 }}>
                Each answer is grounded in the same retrieved evidence used for the explanation.
              </p>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              {SUGGESTED.map(q => (
                <button
                  key={q}
                  onClick={() => submit(q)}
                  style={{
                    textAlign: "left", padding: "12px 14px", borderRadius: 10,
                    background: C.surface, border: `1px solid ${C.border}`,
                    color: C.text, fontSize: 13, lineHeight: 1.5, cursor: "pointer",
                    transition: "all 120ms ease",
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = C.sageDim;
                    e.currentTarget.style.borderColor = C.sageRing;
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = C.surface;
                    e.currentTarget.style.borderColor = C.border;
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </>
        )}

        {messages.map((m, i) => (
          <div key={i} style={{
            display: "flex",
            flexDirection: m.role === "user" ? "row-reverse" : "row",
            gap: 10,
          }}>
            <div style={{
              width: 28, height: 28, borderRadius: 999,
              background: m.role === "user" ? C.text : C.sage,
              color: "#fff", fontSize: 11, fontWeight: 600,
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}>
              {m.role === "user" ? "U" : "CW"}
            </div>
            <div style={{ maxWidth: "78%" }}>
              <div style={{
                background: m.role === "user" ? C.text : C.surface,
                color: m.role === "user" ? "#FAF7F2" : C.text,
                border: m.role === "user" ? "none" : `1px solid ${C.border}`,
                borderRadius: 12,
                borderTopRightRadius: m.role === "user" ? 4 : 12,
                borderTopLeftRadius: m.role === "assistant" ? 4 : 12,
                padding: "10px 14px", fontSize: 13.5, lineHeight: 1.6,
              }}>
                {m.content}
              </div>
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: "flex", gap: 10 }}>
            <div style={{
              width: 28, height: 28, borderRadius: 999, background: C.sage,
              color: "#fff", fontSize: 11, fontWeight: 600,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              CW
            </div>
            <div style={{
              background: C.surface, border: `1px solid ${C.border}`,
              borderRadius: 12, padding: "10px 14px",
              display: "flex", gap: 4, alignItems: "center",
            }}>
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          </div>
        )}

        {error && (
          <p style={{
            textAlign: "center", fontSize: 12, color: C.clay,
            background: C.clayDim, border: `1px solid ${C.clayRing}`,
            borderRadius: 8, padding: "8px 14px",
          }}>
            {error}
          </p>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={e => { e.preventDefault(); submit(input); }}
        style={{
          flexShrink: 0, padding: "12px 24px 18px",
          borderTop: `1px solid ${C.border}`, background: C.surface,
          display: "flex", gap: 10, alignItems: "flex-end",
        }}
      >
        <div style={{ flex: 1, position: "relative" }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(input); }
            }}
            rows={1}
            placeholder={clauseText ? `Ask about this clause… (Enter to send, Shift+Enter for new line)` : "Ask a question… (Enter to send)"}
            style={{
              width: "100%", resize: "none", fontFamily: "var(--font-ui)",
              fontSize: 13.5, lineHeight: 1.5, padding: "11px 13px",
              minHeight: 44, borderRadius: 10,
              border: `1px solid ${C.borderMid}`, background: C.surface,
              color: C.text, outline: "none", transition: "border-color 150ms ease",
            }}
            onFocus={e => (e.target.style.borderColor = C.sage)}
            onBlur={e => (e.target.style.borderColor = C.borderMid)}
          />
        </div>
        <button
          type="submit"
          disabled={!input.trim() || loading}
          style={{
            width: 44, height: 44, borderRadius: 10, border: "none",
            background: input.trim() ? C.sage : C.surface3,
            color: input.trim() ? "#fff" : C.text3,
            display: "flex", alignItems: "center", justifyContent: "center",
            cursor: input.trim() ? "pointer" : "not-allowed",
            transition: "all 150ms ease",
          }}
        >
          <Icon name="send" size={16} color="currentColor" />
        </button>
      </form>
    </div>
  );
}
