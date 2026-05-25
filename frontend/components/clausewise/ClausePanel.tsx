"use client";

import { useMemo } from "react";
import Icon from "./Icon";
import { C, TYPE_HUE } from "@/lib/tokens";
import type { ClauseItem } from "@/lib/api";

interface Props {
  clauses: ClauseItem[];
  selected: ClauseItem | null;
  onSelect: (clause: ClauseItem) => void;
  contractName?: string;
  loading?: boolean;
}

export default function ClausePanel({ clauses, selected, onSelect, contractName, loading }: Props) {
  const byType = useMemo(() => {
    const m: Record<string, number> = {};
    clauses.forEach(c => { m[c.clause_type] = (m[c.clause_type] || 0) + 1; });
    return m;
  }, [clauses]);

  return (
    <aside style={{
      width: 290,
      flexShrink: 0,
      background: C.surface,
      borderRight: `1px solid ${C.border}`,
      display: "flex",
      flexDirection: "column",
      height: "100%",
    }}>
      {/* Contract summary */}
      <div style={{ padding: "16px 18px 12px", borderBottom: `1px solid ${C.border}` }}>
        <p style={{
          fontSize: 10, fontWeight: 600, letterSpacing: "0.12em",
          textTransform: "uppercase", color: C.text3, marginBottom: 6,
        }}>
          Document
        </p>
        <p style={{
          fontFamily: "var(--font-display)", fontSize: 17, fontWeight: 500,
          color: C.text, letterSpacing: "-0.005em", marginBottom: 10, lineHeight: 1.25,
        }}>
          {contractName || "No document loaded"}
        </p>
        <div style={{ display: "flex", gap: 14, fontSize: 11.5, color: C.text2 }}>
          <span>
            <span style={{ fontFamily: "var(--font-mono)", color: C.text, fontWeight: 600 }}>
              {clauses.length}
            </span>{" "}clauses
          </span>
          <span>
            <span style={{ fontFamily: "var(--font-mono)", color: C.text, fontWeight: 600 }}>
              {Object.keys(byType).length}
            </span>{" "}types
          </span>
        </div>
      </div>

      {/* List */}
      <div style={{ flex: 1, overflowY: "auto", padding: "8px 8px 16px" }}>
        {loading ? (
          <div style={{ padding: 10 }}>
            {[1,2,3,4,5].map(i => (
              <div key={i} style={{ padding: 12, borderRadius: 9, marginBottom: 4 }}>
                <div className="skeleton" style={{ height: 10, width: "60%", marginBottom: 8 }} />
                <div className="skeleton" style={{ height: 10, width: "100%", marginBottom: 5 }} />
                <div className="skeleton" style={{ height: 10, width: "80%" }} />
              </div>
            ))}
          </div>
        ) : clauses.length === 0 ? (
          <div style={{
            display: "flex", flexDirection: "column", alignItems: "center",
            justifyContent: "center", height: "100%", padding: 24, textAlign: "center", gap: 12,
          }}>
            <div style={{
              width: 48, height: 48, borderRadius: 14, background: C.surface2,
              border: `1px solid ${C.border}`, display: "flex",
              alignItems: "center", justifyContent: "center",
            }}>
              <Icon name="file" size={20} color={C.text3} />
            </div>
            <p style={{ fontSize: 12.5, color: C.text2, lineHeight: 1.5 }}>
              Upload a contract to view its clauses here
            </p>
          </div>
        ) : (
          clauses.map(c => {
            const isSelected = selected?.clause_id === c.clause_id;
            const hue = TYPE_HUE[c.clause_type] || TYPE_HUE.unknown;
            return (
              <button
                key={c.clause_id}
                onClick={() => onSelect(c)}
                style={{
                  width: "100%", textAlign: "left",
                  padding: "11px 12px", borderRadius: 9, marginBottom: 3,
                  border: isSelected ? `1px solid ${hue}40` : "1px solid transparent",
                  background: isSelected ? `${hue}10` : "transparent",
                  cursor: "pointer", display: "flex", gap: 10, alignItems: "flex-start",
                  transition: "background 120ms ease, border-color 120ms ease",
                }}
                onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = C.surface2; }}
                onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = "transparent"; }}
              >
                <div style={{
                  width: 4, alignSelf: "stretch", borderRadius: 2,
                  background: isSelected ? hue : `${hue}40`, flexShrink: 0,
                  marginTop: 2, minHeight: 28,
                }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                    <span style={{
                      fontSize: 10, fontWeight: 700, letterSpacing: "0.06em",
                      textTransform: "uppercase",
                      color: isSelected ? hue : C.text2, lineHeight: 1,
                    }}>
                      {c.clause_type.replace(/_/g, " ")}
                    </span>
                    <span style={{
                      marginLeft: "auto", fontFamily: "var(--font-mono)",
                      fontSize: 10, color: C.text3,
                    }}>
                      {c.word_count}w
                    </span>
                  </div>
                  <p style={{
                    fontSize: 12, lineHeight: 1.55,
                    color: isSelected ? C.text : C.text2,
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                  }}>
                    {c.text}
                  </p>
                </div>
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}
