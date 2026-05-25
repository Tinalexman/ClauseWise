"use client";

import { useState } from "react";
import Icon from "./Icon";
import { C } from "@/lib/tokens";
import type { EvidenceUsage } from "@/lib/api";

interface Props {
  evidenceUsed: EvidenceUsage[];
  loading?: boolean;
}

export default function EvidencePanel({ evidenceUsed, loading }: Props) {
  const [open, setOpen] = useState<string | null>(
    evidenceUsed[0]?.evidence_id ?? null
  );

  if (loading) {
    return (
      <div style={{ padding: "24px 28px", maxWidth: 760 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[1,2,3].map(i => (
            <div key={i} className="skeleton" style={{ height: 52, borderRadius: 12 }} />
          ))}
        </div>
      </div>
    );
  }

  if (evidenceUsed.length === 0) {
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
          <Icon name="database" size={22} color={C.text3} />
        </div>
        <p style={{ fontSize: 13, color: C.text2, lineHeight: 1.6 }}>
          Run analysis to surface supporting legal context.
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: "24px 28px", maxWidth: 760 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 14 }}>
        <p style={{
          fontSize: 10, fontWeight: 600, letterSpacing: "0.12em",
          textTransform: "uppercase", color: C.text3,
        }}>
          {evidenceUsed.length} evidence item{evidenceUsed.length !== 1 ? "s" : ""} retrieved
        </p>
        <span style={{ fontSize: 11, color: C.text3, fontFamily: "var(--font-mono)" }}>
          Config 5 · cross-encoder reranked
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {evidenceUsed.map(ev => {
          const isOpen = open === ev.evidence_id;
          const pct = Math.round(ev.relevance_score * 100);
          return (
            <div key={ev.evidence_id} style={{
              background: C.surface,
              border: `1px solid ${isOpen ? C.borderMid : C.border}`,
              borderRadius: 12, overflow: "hidden",
              transition: "border-color 150ms ease",
            }}>
              <button
                onClick={() => setOpen(isOpen ? null : ev.evidence_id)}
                style={{
                  width: "100%", display: "flex", alignItems: "center", gap: 14,
                  padding: "14px 16px", background: "none", border: "none",
                  cursor: "pointer", textAlign: "left",
                }}
              >
                <span style={{
                  fontFamily: "var(--font-mono)", fontSize: 11.5,
                  color: C.sage, fontWeight: 600, flexShrink: 0, minWidth: 200,
                }}>
                  {ev.evidence_id}
                </span>
                <div style={{ flex: 1 }} />
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                  <div style={{
                    width: 88, height: 5, background: C.surface3,
                    borderRadius: 999, overflow: "hidden",
                  }}>
                    <div style={{
                      width: `${pct}%`, height: "100%",
                      background: `linear-gradient(90deg, ${C.sage}, ${C.sageHi})`,
                    }} />
                  </div>
                  <span style={{
                    fontFamily: "var(--font-mono)", fontSize: 11,
                    color: C.text, fontWeight: 600, width: 32, textAlign: "right",
                  }}>
                    {pct}%
                  </span>
                  <Icon
                    name="chevDown"
                    size={14}
                    color={C.text3}
                    style={{
                      transition: "transform 200ms",
                      transform: isOpen ? "rotate(180deg)" : "none",
                    }}
                  />
                </div>
              </button>

              {isOpen && (
                <div style={{
                  padding: "0 16px 16px 16px",
                  borderTop: `1px solid ${C.border}`,
                  background: C.surface2,
                }}>
                  <div style={{
                    display: "flex", gap: 14, paddingTop: 12,
                    marginBottom: 10, fontSize: 11, color: C.text2,
                  }}>
                    <span>
                      <span style={{ color: C.text3 }}>Score </span>
                      <span style={{ color: C.text, fontWeight: 500, fontFamily: "var(--font-mono)" }}>
                        {ev.relevance_score.toFixed(4)}
                      </span>
                    </span>
                    <span>
                      <span style={{ color: C.text3 }}>ID </span>
                      <span style={{ color: C.text, fontWeight: 500 }}>{ev.evidence_id}</span>
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
