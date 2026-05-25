"use client";

import Icon from "./Icon";
import { C } from "@/lib/tokens";
import type { ClauseItem, ExplanationOutput } from "@/lib/api";

interface Props {
  clause: ClauseItem | null;
  explanation: ExplanationOutput | null;
}

export default function ComparisonView({ clause, explanation }: Props) {
  if (!clause || !explanation) {
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
          <Icon name="split" size={22} color={C.text3} />
        </div>
        <p style={{ fontSize: 13, color: C.text2, lineHeight: 1.6 }}>
          Select and analyze a clause to compare.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", height: "100%" }}>
      {/* Original */}
      <div style={{
        padding: "26px 28px", overflowY: "auto",
        borderRight: `1px solid ${C.border}`, background: C.surface,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
          <span style={{ width: 8, height: 8, borderRadius: 999, background: C.text3 }} />
          <span style={{
            fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
            textTransform: "uppercase", color: C.text3,
          }}>
            Original legal text
          </span>
        </div>
        <p style={{
          fontFamily: "var(--font-display)", fontSize: 17, lineHeight: 1.8,
          color: C.text2,
        }}>
          {clause.text}
        </p>
        <div style={{
          display: "flex", gap: 14, fontSize: 11, color: C.text3,
          marginTop: 18, paddingTop: 14, borderTop: `1px dashed ${C.border}`,
        }}>
          <span>{clause.word_count} words</span>
          <span style={{ textTransform: "capitalize" }}>{clause.clause_type.replace(/_/g, " ")}</span>
        </div>
      </div>

      {/* Plain English */}
      <div style={{ padding: "26px 28px", overflowY: "auto", background: C.sageDimer }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
          <span style={{ width: 8, height: 8, borderRadius: 999, background: C.sage }} />
          <span style={{
            fontSize: 10, fontWeight: 700, letterSpacing: "0.12em",
            textTransform: "uppercase", color: C.sage,
          }}>
            Plain English · ClauseWise
          </span>
        </div>
        <p style={{ fontFamily: "var(--font-display)", fontSize: 17, lineHeight: 1.8, color: C.text }}>
          {explanation.plain_english}
        </p>
        {explanation.user_implications && (
          <p style={{
            fontFamily: "var(--font-ui)", fontSize: 13.5, lineHeight: 1.7,
            color: C.text2, marginTop: 14, paddingTop: 14,
            borderTop: `1px dashed ${C.sageRing}`, fontStyle: "italic",
          }}>
            {explanation.user_implications}
          </p>
        )}
        <div style={{
          display: "flex", gap: 14, fontSize: 11, color: C.text3,
          marginTop: 18, paddingTop: 14, borderTop: `1px dashed ${C.sageRing}`,
        }}>
          <span>FK grade {explanation.readability.flesch_kincaid_grade.toFixed(1)}</span>
          <span>{explanation.confidence} confidence</span>
        </div>
      </div>
    </div>
  );
}
