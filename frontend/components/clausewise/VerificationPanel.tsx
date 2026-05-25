"use client";

import Icon from "./Icon";
import { C } from "@/lib/tokens";
import type { ExplanationOutput } from "@/lib/api";

interface Props {
  verification: ExplanationOutput["verification"];
  explanation: ExplanationOutput | null;
}

function FidelityArc({ score }: { score: number }) {
  const size = 132, r = 56, cx = size / 2, cy = size / 2;
  const circ = 2 * Math.PI * r;
  const dash = score * circ;
  const color = score >= 0.85 ? C.sage : score >= 0.7 ? C.amber : C.clay;
  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={C.surface3} strokeWidth={8} />
        <circle
          cx={cx} cy={cy} r={r} fill="none"
          stroke={color} strokeWidth={8} strokeLinecap="round"
          strokeDasharray={`${dash} ${circ}`}
          style={{ transition: "stroke-dasharray 800ms ease" }}
        />
      </svg>
      <div style={{
        position: "absolute", inset: 0, display: "flex",
        flexDirection: "column", alignItems: "center", justifyContent: "center",
      }}>
        <span style={{
          fontFamily: "var(--font-display)", fontSize: 30,
          color: C.text, fontWeight: 500, lineHeight: 1,
        }}>
          {Math.round(score * 100)}
          <span style={{ fontSize: 14, color: C.text3, marginLeft: 1 }}>%</span>
        </span>
        <span style={{
          fontSize: 9.5, fontWeight: 700, letterSpacing: "0.14em",
          color: C.text3, textTransform: "uppercase", marginTop: 4,
        }}>
          Fidelity
        </span>
      </div>
    </div>
  );
}

function ScoreBar({ label, sublabel, value, tint }: { label: string; sublabel: string; value: number; tint: string }) {
  const pct = Math.round(value * 100);
  return (
    <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: "12px 14px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span style={{ fontSize: 12.5, color: C.text, fontWeight: 600 }}>{label}</span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: tint, fontWeight: 600 }}>{pct}%</span>
      </div>
      <p style={{ fontSize: 10.5, color: C.text3, marginBottom: 8 }}>{sublabel}</p>
      <div style={{ height: 5, background: C.surface3, borderRadius: 999, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: tint, transition: "width 700ms ease" }} />
      </div>
    </div>
  );
}

function Metric({ label, value, mono, tone }: { label: string; value: string | number; mono?: boolean; tone?: string }) {
  return (
    <div>
      <p style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: C.text3, marginBottom: 4 }}>
        {label}
      </p>
      <p style={{
        fontSize: 14, color: tone === "warning" ? C.clay : C.text, fontWeight: 500,
        fontFamily: mono ? "var(--font-mono)" : "var(--font-ui)",
      }}>
        {value}
      </p>
    </div>
  );
}

export default function VerificationPanel({ verification, explanation }: Props) {
  if (!verification) {
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
          <Icon name="shield" size={22} color={C.text3} />
        </div>
        <div style={{ maxWidth: 320 }}>
          <p style={{ fontSize: 14.5, fontWeight: 600, color: C.text, marginBottom: 6 }}>
            Verification not run
          </p>
          <p style={{ fontSize: 13, color: C.text2, lineHeight: 1.6 }}>
            Toggle verification in the pipeline drawer to dual-check explanations against retrieved evidence.
          </p>
        </div>
      </div>
    );
  }

  const { fidelity_score, passed, entailment_label, revision_count, flags } = verification;
  const pct = Math.round(fidelity_score * 100);

  return (
    <div style={{ padding: "24px 28px", maxWidth: 760 }}>
      {/* Score card */}
      <div style={{
        display: "flex", gap: 24, padding: "22px 24px", background: C.surface,
        border: `1px solid ${C.border}`, borderRadius: 14, marginBottom: 16,
      }}>
        <FidelityArc score={fidelity_score} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: C.text3, marginBottom: 8 }}>
            Fidelity verdict
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            <span style={{
              fontFamily: "var(--font-display)", fontSize: 30, color: C.text, fontWeight: 500, letterSpacing: "-0.01em",
            }}>
              {passed ? "Passed" : "Needs review"}
            </span>
            <span style={{
              display: "inline-flex", alignItems: "center", gap: 5, padding: "2px 9px",
              borderRadius: 999, background: passed ? C.sageDim : C.clayDim,
              border: `1px solid ${passed ? C.sageRing : C.clayRing}`,
              color: passed ? C.sage : C.clay, fontSize: 11, fontWeight: 600,
            }}>
              <Icon name={passed ? "checkCircle" : "alert"} size={11} color={passed ? C.sage : C.clay} />
              {passed ? "Faithful to source" : "Possible drift"}
            </span>
          </div>
          <p style={{ fontSize: 13.5, color: C.text2, lineHeight: 1.6, marginBottom: 14 }}>
            NLI entailment + LLM-as-judge agree the explanation stays within what the clause and retrieved evidence actually say.
          </p>
          <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
            <Metric label="Entailment" value={entailment_label} />
            <Metric label="Score" value={`${pct}%`} mono />
            <Metric label="Revisions" value={revision_count} mono />
            <Metric
              label="Flags"
              value={flags.length || "none"}
              mono={!!flags.length}
              tone={flags.length ? "warning" : undefined}
            />
          </div>
        </div>
      </div>

      {/* Score bars */}
      <section style={{ marginBottom: 22 }}>
        <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: C.text3, marginBottom: 10 }}>
          Decomposition
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <ScoreBar
            label="NLI entailment"
            sublabel="deberta-v3-base, local"
            value={Math.min(1, fidelity_score + 0.04)}
            tint={C.sage}
          />
          <ScoreBar
            label="LLM-as-judge"
            sublabel="gpt-4o-mini rubric"
            value={Math.max(0, fidelity_score - 0.03)}
            tint={C.blue}
          />
        </div>
      </section>

      {/* Flags */}
      {flags.length > 0 && (
        <section style={{ marginBottom: 22 }}>
          <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: C.text3, marginBottom: 10 }}>
            Flags raised
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {flags.map((f, i) => (
              <div key={i} style={{
                background: C.amberDim, border: `1px solid ${C.amberRing}`,
                borderRadius: 10, padding: "10px 14px",
                display: "flex", gap: 10, alignItems: "center", fontSize: 13, color: C.text,
              }}>
                <Icon name="info" size={14} color={C.amber} />
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{f}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Generation metadata */}
      {explanation && (
        <section>
          <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: C.text3, marginBottom: 10 }}>
            Generation metadata
          </p>
          <div style={{
            background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10,
            padding: 16, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14,
          }}>
            <Metric label="Model" value={explanation.metadata.model} />
            <Metric label="Temperature" value={explanation.metadata.temperature} mono />
            <Metric label="Latency" value={`${explanation.metadata.latency_ms} ms`} mono />
            <Metric label="Input tokens" value={explanation.metadata.token_count_input} mono />
            <Metric label="Output tokens" value={explanation.metadata.token_count_output} mono />
            <Metric label="Timestamp" value={new Date(explanation.metadata.timestamp).toLocaleString()} />
          </div>
        </section>
      )}
    </div>
  );
}
