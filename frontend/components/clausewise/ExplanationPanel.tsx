"use client";

import Icon from "./Icon";
import { C } from "@/lib/tokens";
import type { ExplanationOutput } from "@/lib/api";

interface Props {
  explanation: ExplanationOutput | null;
  loading?: boolean;
}

export default function ExplanationPanel({ explanation, loading }: Props) {
  if (loading) {
    return (
      <div style={{ padding: "24px 28px", maxWidth: 760 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="skeleton" style={{ height: 11, width: "32%" }} />
          <div className="skeleton" style={{ height: 18, width: "100%" }} />
          <div className="skeleton" style={{ height: 18, width: "92%" }} />
          <div className="skeleton" style={{ height: 18, width: "78%" }} />
          <div style={{ height: 12 }} />
          <div className="skeleton" style={{ height: 11, width: "28%" }} />
          <div style={{
            height: 92, background: C.surface, border: `1px solid ${C.border}`,
            borderRadius: 12, padding: 14, display: "flex", flexDirection: "column", gap: 8,
          }}>
            <div className="skeleton" style={{ height: 10, width: "20%" }} />
            <div className="skeleton" style={{ height: 10, width: "92%" }} />
            <div className="skeleton" style={{ height: 10, width: "84%" }} />
          </div>
          <div style={{ height: 12 }} />
          <div className="skeleton" style={{ height: 11, width: "22%" }} />
          {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height: 11, width: "100%" }} />)}
        </div>
        <div style={{
          marginTop: 24, display: "inline-flex", alignItems: "center", gap: 10,
          padding: "10px 14px", borderRadius: 10, background: C.sageDim,
          border: `1px solid ${C.sageRing}`, color: C.sage, fontSize: 12.5, fontWeight: 600,
        }}>
          <span className="spinner" />
          Running pipeline · retrieve → classify → generate
          <span style={{ color: C.text3, fontWeight: 500, marginLeft: 4 }}>(~1.8s typical)</span>
        </div>
      </div>
    );
  }

  if (!explanation) {
    return (
      <div style={{
        flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
        justifyContent: "center", height: "100%", padding: 32, textAlign: "center", gap: 14,
      }}>
        <div style={{
          width: 56, height: 56, borderRadius: 16, background: C.surface2,
          border: `1px solid ${C.border}`, display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Icon name="book" size={22} color={C.text3} />
        </div>
        <div style={{ maxWidth: 320 }}>
          <p style={{ fontSize: 14.5, fontWeight: 600, color: C.text, marginBottom: 6 }}>
            Select a clause to begin
          </p>
          <p style={{ fontSize: 13, color: C.text2, lineHeight: 1.6 }}>
            Choose a clause from the sidebar to see its plain-English explanation.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: "24px 28px", maxWidth: 760 }}>
      {/* Plain English */}
      <section style={{ marginBottom: 22 }}>
        <p style={{
          fontSize: 10, fontWeight: 600, letterSpacing: "0.12em",
          textTransform: "uppercase", color: C.text3, marginBottom: 10,
        }}>
          Plain English
        </p>
        <p style={{
          fontFamily: "var(--font-display)", fontSize: 22, lineHeight: 1.55,
          color: C.text, letterSpacing: "-0.005em",
        }}>
          {explanation.plain_english}
        </p>
      </section>

      {/* What this means for you */}
      {explanation.user_implications && (
        <section style={{ marginBottom: 22 }}>
          <div style={{
            background: C.surface2, border: `1px solid ${C.border}`,
            borderRadius: 12, padding: "16px 18px", borderLeft: `3px solid ${C.sage}`,
          }}>
            <p style={{
              fontSize: 10, fontWeight: 600, letterSpacing: "0.12em",
              textTransform: "uppercase", color: C.sage, marginBottom: 8,
            }}>
              What this means for you
            </p>
            <p style={{ fontSize: 14.5, color: C.text, lineHeight: 1.7 }}>
              {explanation.user_implications}
            </p>
          </div>
        </section>
      )}

      {/* Before you sign */}
      {explanation.check_before_signing.length > 0 && (
        <section style={{ marginBottom: 22 }}>
          <p style={{
            fontSize: 10, fontWeight: 600, letterSpacing: "0.12em",
            textTransform: "uppercase", color: C.text3, marginBottom: 10,
          }}>
            Before you sign
          </p>
          <ul style={{ display: "flex", flexDirection: "column", gap: 10, listStyle: "none" }}>
            {explanation.check_before_signing.map((item, i) => (
              <li key={i} style={{
                display: "flex", gap: 12, alignItems: "flex-start",
                padding: "12px 14px", background: C.surface,
                border: `1px solid ${C.border}`, borderRadius: 10,
              }}>
                <div style={{
                  width: 22, height: 22, borderRadius: 999, background: C.sageDim,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexShrink: 0, marginTop: 1,
                }}>
                  <Icon name="check" size={12} color={C.sage} strokeWidth={2.5} />
                </div>
                <p style={{ fontSize: 14, color: C.text, lineHeight: 1.6, flex: 1 }}>{item}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Legal advice banner */}
      {explanation.seek_legal_advice.recommended && explanation.seek_legal_advice.reason && (
        <div style={{
          background: C.clayDim, border: `1px solid ${C.clayRing}`,
          borderRadius: 12, padding: "14px 16px", display: "flex", gap: 12,
        }}>
          <Icon name="alert" size={18} color={C.clay} style={{ flexShrink: 0, marginTop: 2 }} />
          <p style={{ fontSize: 13.5, color: C.text, lineHeight: 1.65 }}>
            <span style={{ fontWeight: 600, color: C.clay }}>Counsel recommended — </span>
            {explanation.seek_legal_advice.reason}
          </p>
        </div>
      )}
    </div>
  );
}
