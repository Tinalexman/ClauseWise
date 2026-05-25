"use client";

import Icon from "./Icon";
import { C, SEVERITY } from "@/lib/tokens";
import type { RiskDetail } from "@/lib/api";

interface Props {
  risks: RiskDetail[];
  loading?: boolean;
}

const SEV_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export default function RiskPanel({ risks, loading }: Props) {
  if (loading) {
    return (
      <div style={{ padding: "24px 28px", maxWidth: 760 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {[1,2].map(i => (
            <div key={i} style={{ borderRadius: 12, border: `1px solid ${C.border}`, overflow: "hidden" }}>
              <div className="skeleton" style={{ height: 3, width: "100%", borderRadius: 0 }} />
              <div style={{ padding: "16px 18px", display: "flex", flexDirection: "column", gap: 8 }}>
                <div className="skeleton" style={{ height: 11, width: "24%" }} />
                <div className="skeleton" style={{ height: 18, width: "72%" }} />
                <div className="skeleton" style={{ height: 11, width: "100%" }} />
                <div className="skeleton" style={{ height: 11, width: "88%" }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (risks.length === 0) {
    return (
      <div style={{
        flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
        justifyContent: "center", height: "100%", padding: 32, textAlign: "center", gap: 14,
      }}>
        <div style={{
          width: 56, height: 56, borderRadius: 16, background: C.sageDim,
          border: `1px solid ${C.sageRing}`, display: "flex",
          alignItems: "center", justifyContent: "center",
        }}>
          <Icon name="shield" size={22} color={C.sage} />
        </div>
        <div style={{ maxWidth: 320 }}>
          <p style={{ fontSize: 14.5, fontWeight: 600, color: C.text, marginBottom: 6 }}>
            No risks identified
          </p>
          <p style={{ fontSize: 13, color: C.text2, lineHeight: 1.6 }}>
            This clause appears consumer-friendly. We still recommend reading it carefully before signing.
          </p>
        </div>
      </div>
    );
  }

  const sorted = [...risks].sort((a, b) => (SEV_ORDER[a.severity] ?? 4) - (SEV_ORDER[b.severity] ?? 4));
  const counts = risks.reduce<Record<string, number>>((acc, r) => {
    acc[r.severity] = (acc[r.severity] || 0) + 1;
    return acc;
  }, {});

  return (
    <div style={{ padding: "24px 28px", maxWidth: 760 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 14 }}>
        <p style={{
          fontSize: 10, fontWeight: 600, letterSpacing: "0.12em",
          textTransform: "uppercase", color: C.text3,
        }}>
          {risks.length} risk{risks.length !== 1 ? "s" : ""} detected
        </p>
        <div style={{ display: "inline-flex", gap: 12, fontSize: 11, color: C.text2 }}>
          {Object.entries(SEV_ORDER).map(([sev]) => {
            const count = counts[sev];
            if (!count) return null;
            const cfg = SEVERITY[sev as keyof typeof SEVERITY];
            return (
              <span key={sev} style={{ display: "inline-flex", gap: 5, alignItems: "center" }}>
                <span style={{ width: 8, height: 8, borderRadius: 999, background: cfg.dot }} />
                <span style={{ fontFamily: "var(--font-mono)", color: C.text }}>{count}</span>
                <span style={{ textTransform: "capitalize" }}>{cfg.label}</span>
              </span>
            );
          }).filter(Boolean)}
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {sorted.map((risk, i) => {
          const cfg = SEVERITY[risk.severity as keyof typeof SEVERITY] || SEVERITY.medium;
          return (
            <div key={i} style={{
              borderRadius: 12, border: `1px solid ${C.border}`,
              background: C.surface, overflow: "hidden",
            }}>
              <div style={{ height: 3, background: cfg.dot, width: "100%" }} />
              <div style={{ padding: "16px 18px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                  <span style={{
                    display: "inline-flex", alignItems: "center", gap: 5,
                    padding: "2px 8px", borderRadius: 999,
                    background: cfg.bg, border: `1px solid ${cfg.ring}`,
                    color: cfg.text, fontSize: 10.5, fontWeight: 700,
                    letterSpacing: "0.06em", textTransform: "uppercase",
                  }}>
                    {cfg.label}
                  </span>
                  <span style={{
                    fontFamily: "var(--font-display)", fontSize: 17,
                    color: C.text, fontWeight: 500,
                  }}>
                    {risk.risk_category.replace(/_/g, " ")}
                  </span>
                </div>
                <p style={{ fontSize: 14.5, color: C.text, lineHeight: 1.65, marginBottom: 12 }}>
                  {risk.explanation}
                </p>
                <div style={{
                  paddingTop: 12, borderTop: `1px dashed ${C.border}`,
                  display: "flex", gap: 10, alignItems: "flex-start",
                }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: "0.1em",
                    textTransform: "uppercase", color: C.text3,
                    flexShrink: 0, marginTop: 2,
                  }}>
                    Action
                  </span>
                  <p style={{ fontSize: 13.5, color: C.text2, lineHeight: 1.65 }}>
                    {risk.recommended_action}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
