"use client";

import { C } from "@/lib/tokens";

type StudyGroup = "A" | "B" | "C" | "D";

const STUDY_INFO: Record<StudyGroup, { label: string; desc: string }> = {
  A: { label: "Baseline",             desc: "Clause text only" },
  B: { label: "Explanation",          desc: "+ plain-English explanation" },
  C: { label: "Full minus evidence",  desc: "+ risks · compare · ask" },
  D: { label: "Full system",          desc: "all panels including evidence & verification" },
};

export default function StudyControls({
  group,
  onChange,
  sessionId = "sess_000000",
}: {
  group: StudyGroup;
  onChange: (g: StudyGroup) => void;
  sessionId?: string;
}) {
  return (
    <div style={{
      flexShrink: 0,
      display: "flex",
      alignItems: "center",
      gap: 14,
      padding: "0 24px",
      height: 36,
      borderBottom: `1px solid ${C.border}`,
      background: C.surface2,
    }}>
      <span style={{
        fontSize: 9.5,
        fontWeight: 700,
        letterSpacing: "0.14em",
        textTransform: "uppercase",
        color: C.text3,
      }}>
        Study condition
      </span>

      <div style={{
        display: "inline-flex",
        padding: 2,
        background: C.surface,
        borderRadius: 7,
        border: `1px solid ${C.border}`,
      }}>
        {(["A", "B", "C", "D"] as StudyGroup[]).map(g => {
          const active = group === g;
          return (
            <button
              key={g}
              onClick={() => onChange(g)}
              style={{
                width: 26, height: 22,
                borderRadius: 5,
                border: "none",
                background: active ? C.sage : "transparent",
                color: active ? "#fff" : C.text2,
                fontSize: 11,
                fontWeight: 700,
                cursor: "pointer",
                transition: "all 120ms ease",
              }}
            >
              {g}
            </button>
          );
        })}
      </div>

      <span style={{ fontSize: 12, color: C.text }}>
        {STUDY_INFO[group].label}
        <span style={{ color: C.text3, marginLeft: 7 }}>— {STUDY_INFO[group].desc}</span>
      </span>

      <div style={{ flex: 1 }} />

      <span style={{ fontSize: 10.5, color: C.text3, fontFamily: "var(--font-mono)" }}>
        session · {sessionId}
      </span>
    </div>
  );
}

export function getPanelVisibility(group: StudyGroup) {
  return {
    showExplanation:  group !== "A",
    showRisks:        group === "C" || group === "D",
    showEvidence:     group === "D",
    showVerification: group === "D",
    showComparison:   group === "C" || group === "D",
    showFollowUp:     group === "C" || group === "D",
  };
}
