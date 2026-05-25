"use client";

import { useState, useEffect } from "react";
import Icon from "./Icon";
import { C } from "@/lib/tokens";

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (text: string) => void;
}

export default function PasteModal({ open, onClose, onSubmit }: Props) {
  const [text, setText] = useState("");

  useEffect(() => {
    if (!open) setText("");
  }, [open]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const wordCount = text.split(/\s+/).filter(Boolean).length;

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed", inset: 0,
          background: "rgba(20,18,15,0.32)",
          backdropFilter: "blur(4px)", zIndex: 70,
        }}
      />
      <div style={{
        position: "fixed", top: "50%", left: "50%",
        transform: "translate(-50%, -50%)",
        width: 560, maxWidth: "90vw",
        background: C.surface, borderRadius: 16,
        boxShadow: "0 24px 60px rgba(20,18,15,0.18)",
        zIndex: 71, overflow: "hidden",
      }}>
        {/* Header */}
        <div style={{
          padding: "18px 22px", borderBottom: `1px solid ${C.border}`,
          display: "flex", alignItems: "center", gap: 10,
        }}>
          <Icon name="plus" size={16} color={C.sage} />
          <p style={{
            fontFamily: "var(--font-display)", fontSize: 19,
            fontWeight: 500, color: C.text, flex: 1,
          }}>
            Paste a clause
          </p>
          <button
            onClick={onClose}
            style={{
              width: 28, height: 28, borderRadius: 7, border: "none",
              background: "transparent", color: C.text2, cursor: "pointer",
            }}
          >
            <Icon name="x" size={14} color={C.text2} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: 22 }}>
          <textarea
            autoFocus
            value={text}
            onChange={e => setText(e.target.value)}
            rows={8}
            placeholder="Paste a single clause here…"
            style={{
              width: "100%", resize: "vertical", minHeight: 180,
              fontFamily: "var(--font-display)", fontSize: 14.5, lineHeight: 1.7,
              padding: 14, borderRadius: 10,
              border: `1px solid ${C.borderMid}`, outline: "none",
              color: C.text, background: C.surface,
              transition: "border-color 150ms ease",
            }}
            onFocus={e => (e.target.style.borderColor = C.sage)}
            onBlur={e => (e.target.style.borderColor = C.borderMid)}
          />
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 14 }}>
            <span style={{ fontSize: 11, color: C.text3, fontFamily: "var(--font-mono)" }}>
              {wordCount} words
            </span>
            <div style={{ flex: 1 }} />
            <button
              onClick={onClose}
              style={{
                padding: "9px 16px", borderRadius: 9,
                border: `1px solid ${C.borderMid}`, background: C.surface,
                color: C.text2, fontSize: 13, fontWeight: 500, cursor: "pointer",
              }}
            >
              Cancel
            </button>
            <button
              disabled={!text.trim()}
              onClick={() => onSubmit(text.trim())}
              style={{
                padding: "9px 18px", borderRadius: 9,
                border: `1px solid ${text.trim() ? C.sage : C.borderMid}`,
                background: text.trim() ? C.sage : C.surface2,
                color: text.trim() ? "#fff" : C.text3,
                fontSize: 13, fontWeight: 600,
                cursor: text.trim() ? "pointer" : "not-allowed",
                transition: "all 150ms ease",
              }}
            >
              Analyse clause
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
