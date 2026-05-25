"use client";

import Icon from "./Icon";
import { C, SEVERITY } from "@/lib/tokens";
import type { ExplanationOutput, RetrievalConfig, GenerationVariant } from "@/lib/api";

interface PipelineState {
  retrieval: RetrievalConfig;
  retrievalShort: string;
  generation: GenerationVariant;
  generationShort: string;
  verify: boolean;
  k: number;
}

interface Props {
  explanation: ExplanationOutput | null;
  pipeline: PipelineState;
  onOpenConfig: () => void;
}

function FidelityArc({ score }: { score: number }) {
  const size = 80, r = 34, cx = size / 2, cy = size / 2;
  const circ = 2 * Math.PI * r;
  const dash = score * circ;
  const color = score >= 0.85 ? C.sage : score >= 0.7 ? C.amber : C.clay;
  return (
    <div style={{ position: "relative", width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={C.surface3} strokeWidth={5} />
        <circle
          cx={cx} cy={cy} r={r} fill="none"
          stroke={color} strokeWidth={5} strokeLinecap="round"
          strokeDasharray={`${dash} ${circ}`}
          style={{ transition: "stroke-dasharray 800ms ease" }}
        />
      </svg>
      <div style={{
        position: "absolute", inset: 0, display: "flex",
        flexDirection: "column", alignItems: "center", justifyContent: "center",
      }}>
        <span style={{ fontFamily: "var(--font-display)", fontSize: 18, color: C.text, fontWeight: 500, lineHeight: 1 }}>
          {Math.round(score * 100)}
          <span style={{ fontSize: 10, color: C.text3 }}>%</span>
        </span>
      </div>
    </div>
  );
}

function TileMetric({ label, value, sub, tint }: { label: string; value: string | number; sub: string; tint: string }) {
  return (
    <div style={{
      background: C.surface2, border: `1px solid ${C.border}`,
      borderRadius: 10, padding: "10px 12px",
    }}>
      <p style={{ fontSize: 9.5, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", color: C.text3 }}>
        {label}
      </p>
      <p style={{
        fontFamily: "var(--font-display)", fontSize: 20, color: tint || C.text,
        fontWeight: 500, letterSpacing: "-0.005em", marginTop: 2, textTransform: "capitalize",
      }}>
        {value}
      </p>
      <p style={{ fontSize: 11, color: C.text3, marginTop: 1 }}>
        {sub}
      </p>
    </div>
  );
}

function PipeRow({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12.5 }}>
      <span style={{ color: C.text3 }}>{label}</span>
      <span style={{ color: accent || C.text, fontFamily: "var(--font-mono)", fontWeight: 500 }}>
        {value}
      </span>
    </div>
  );
}

export default function InsightsRail({ explanation, pipeline, onOpenConfig }: Props) {
  if (!explanation) {
    return (
      <aside style={{
        width: 320, flexShrink: 0, background: C.surface,
        borderLeft: `1px solid ${C.border}`, padding: 20,
        display: "flex", flexDirection: "column",
      }}>
        <div style={{
          flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", textAlign: "center", gap: 14,
        }}>
          <div style={{
            width: 56, height: 56, borderRadius: 16, background: C.surface2,
            border: `1px solid ${C.border}`, display: "flex",
            alignItems: "center", justifyContent: "center",
          }}>
            <Icon name="sparkles" size={22} color={C.text3} />
          </div>
          <div style={{ maxWidth: 260 }}>
            <p style={{ fontSize: 14.5, fontWeight: 600, color: C.text, marginBottom: 6 }}>
              Insights appear here
            </p>
            <p style={{ fontSize: 13, color: C.text2, lineHeight: 1.6 }}>
              Select a clause to see fidelity, readability and risk at a glance.
            </p>
          </div>
        </div>
      </aside>
    );
  }

  const conf = explanation.confidence;
  const confValue = conf === "high" ? 1 : conf === "medium" ? 0.6 : 0.3;
  const riskCounts = explanation.risks.reduce<Record<string, number>>((acc, r) => {
    acc[r.severity] = (acc[r.severity] || 0) + 1;
    return acc;
  }, {});
  const highestSev = explanation.risks.length === 0
    ? "low"
    : (["critical", "high", "medium", "low"] as const).find(s => riskCounts[s] > 0) || "low";
  const sevCfg = SEVERITY[highestSev];

  return (
    <aside style={{
      width: 320, flexShrink: 0, background: C.surface,
      borderLeft: `1px solid ${C.border}`,
      display: "flex", flexDirection: "column", overflowY: "auto",
    }}>
      {/* Pipeline */}
      <div style={{ padding: "18px 20px 14px", borderBottom: `1px solid ${C.border}` }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
          <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: C.text3 }}>
            Pipeline
          </p>
          <button
            onClick={onOpenConfig}
            style={{
              background: "none", border: "none", color: C.sage,
              fontSize: 11, fontWeight: 600, cursor: "pointer",
              display: "inline-flex", alignItems: "center", gap: 4,
            }}
          >
            Edit <Icon name="chevRight" size={11} color={C.sage} />
          </button>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <PipeRow label="Retrieval" value={pipeline.retrievalShort} />
          <PipeRow label="Generation" value={pipeline.generationShort} />
          <PipeRow label="Verify" value={pipeline.verify ? "on" : "off"} accent={pipeline.verify ? C.sage : C.text3} />
          <PipeRow label="Top-k" value={pipeline.k} />
        </div>
      </div>

      {/* Fidelity */}
      {explanation.verification && (
        <div style={{
          padding: "16px 20px", borderBottom: `1px solid ${C.border}`,
          display: "flex", alignItems: "center", gap: 14,
        }}>
          <FidelityArc score={explanation.verification.fidelity_score} />
          <div style={{ flex: 1 }}>
            <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: C.text3, marginBottom: 4 }}>
              Fidelity
            </p>
            <p style={{ fontSize: 14, color: C.text, fontWeight: 600, marginBottom: 4 }}>
              {explanation.verification.passed ? "Faithful" : "Needs review"}
            </p>
            <p style={{ fontSize: 11.5, color: C.text2, lineHeight: 1.4 }}>
              {explanation.verification.entailment_label} · {explanation.verification.revision_count} revision
              {explanation.verification.revision_count !== 1 ? "s" : ""}
            </p>
          </div>
        </div>
      )}

      {/* Metric tiles */}
      <div style={{ padding: "16px 20px", borderBottom: `1px solid ${C.border}` }}>
        <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: C.text3, marginBottom: 10 }}>
          This clause
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <TileMetric
            label="Confidence"
            value={conf}
            sub={`${Math.round(confValue * 100)}%`}
            tint={conf === "high" ? C.sage : conf === "medium" ? C.amber : C.clay}
          />
          <TileMetric
            label="Risks"
            value={explanation.risks.length}
            sub={explanation.risks.length === 0 ? "none" : sevCfg.label.toLowerCase()}
            tint={sevCfg.dot}
          />
          <TileMetric
            label="FK grade"
            value={explanation.readability.flesch_kincaid_grade.toFixed(1)}
            sub="reading level"
            tint={C.blue}
          />
          <TileMetric
            label="Latency"
            value={`${(explanation.metadata.latency_ms / 1000).toFixed(2)}s`}
            sub={`${explanation.metadata.token_count_output} tok`}
            tint={C.text2}
          />
        </div>
      </div>

      {/* Top risks */}
      <div style={{ padding: "16px 20px" }}>
        <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: C.text3, marginBottom: 10 }}>
          Highest-severity risks
        </p>
        {explanation.risks.length === 0 ? (
          <p style={{ fontSize: 12.5, color: C.text2, lineHeight: 1.5 }}>
            No flagged risks. Still review the clause yourself before signing.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {explanation.risks.slice(0, 3).map((r, i) => {
              const cfg = SEVERITY[r.severity as keyof typeof SEVERITY] || SEVERITY.medium;
              return (
                <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                  <span style={{
                    width: 4, height: 4, borderRadius: 999, background: cfg.dot,
                    marginTop: 7, flexShrink: 0,
                  }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontSize: 12.5, color: C.text, fontWeight: 500, textTransform: "capitalize" }}>
                      {r.risk_category.replace(/_/g, " ")}
                    </p>
                    <p style={{
                      fontSize: 10.5, color: cfg.text, fontWeight: 600,
                      letterSpacing: "0.06em", textTransform: "uppercase", marginTop: 2,
                    }}>
                      {cfg.label}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </aside>
  );
}
