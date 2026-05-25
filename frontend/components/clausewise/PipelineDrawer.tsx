"use client";

import { useEffect } from "react";
import Icon from "./Icon";
import { C } from "@/lib/tokens";
import { RETRIEVAL_OPTIONS as RO, GENERATION_OPTIONS as GO } from "@/lib/api";
import type { RetrievalConfig, GenerationVariant } from "@/lib/api";

interface PipelineState {
  retrieval: RetrievalConfig;
  retrievalShort: string;
  generation: GenerationVariant;
  generationShort: string;
  verify: boolean;
  k: number;
}

interface Props {
  open: boolean;
  onClose: () => void;
  pipeline: PipelineState;
  onChange: (p: PipelineState) => void;
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      role="switch"
      aria-checked={checked}
      style={{
        width: 38, height: 22, borderRadius: 999, border: "none",
        background: checked ? C.sage : C.borderMid,
        position: "relative", cursor: "pointer", flexShrink: 0,
        transition: "background 200ms ease",
      }}
    >
      <span style={{
        position: "absolute", top: 2,
        left: checked ? 18 : 2, width: 18, height: 18,
        borderRadius: 999, background: "#fff",
        boxShadow: "0 1px 3px rgba(0,0,0,0.15)",
        transition: "left 200ms cubic-bezier(0.32, 0.72, 0.27, 1)",
      }} />
    </button>
  );
}

export default function PipelineDrawer({ open, onClose, pipeline, onChange }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      {/* Scrim */}
      <div
        onClick={onClose}
        style={{
          position: "fixed", inset: 0,
          background: "rgba(20,18,15,0.32)",
          opacity: open ? 1 : 0,
          pointerEvents: open ? "auto" : "none",
          transition: "opacity 200ms ease",
          backdropFilter: open ? "blur(4px)" : "blur(0)",
          zIndex: 60,
        }}
      />

      {/* Drawer */}
      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0, width: 440,
        background: C.surface, borderLeft: `1px solid ${C.border}`,
        boxShadow: "-12px 0 40px rgba(20,18,15,0.10)",
        transform: open ? "translateX(0)" : "translateX(100%)",
        transition: "transform 280ms cubic-bezier(0.32, 0.72, 0.27, 1)",
        zIndex: 61, display: "flex", flexDirection: "column",
      }}>
        {/* Header */}
        <div style={{
          padding: "20px 22px 14px", borderBottom: `1px solid ${C.border}`,
          display: "flex", alignItems: "center", gap: 12,
        }}>
          <Icon name="layers" size={18} color={C.sage} />
          <div style={{ flex: 1 }}>
            <p style={{
              fontFamily: "var(--font-display)", fontSize: 19, fontWeight: 500,
              color: C.text, letterSpacing: "-0.005em",
            }}>
              Pipeline configuration
            </p>
            <p style={{ fontSize: 12, color: C.text2, marginTop: 2 }}>
              Switch retrieval + generation strategy on the fly
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              width: 32, height: 32, borderRadius: 8, border: "none",
              background: "transparent", color: C.text2, cursor: "pointer",
            }}
            onMouseEnter={e => (e.currentTarget.style.background = C.surface2)}
            onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
          >
            <Icon name="x" size={16} color={C.text2} />
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 22px" }}>
          {/* Retrieval */}
          <section style={{ marginBottom: 22 }}>
            <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: C.text3, marginBottom: 10 }}>
              Retrieval config (1–5)
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {RO.map((opt, i) => {
                const active = pipeline.retrieval === opt.value;
                return (
                  <button
                    key={opt.value}
                    onClick={() => onChange({ ...pipeline, retrieval: opt.value, retrievalShort: opt.short })}
                    style={{
                      textAlign: "left", display: "flex", alignItems: "flex-start", gap: 12,
                      padding: "10px 12px", borderRadius: 9,
                      border: `1px solid ${active ? C.sage : C.border}`,
                      background: active ? C.sageDim : C.surface,
                      cursor: "pointer", transition: "all 140ms ease",
                    }}
                  >
                    <span style={{
                      width: 22, height: 22, borderRadius: 999,
                      background: active ? C.sage : C.surface2,
                      color: active ? "#fff" : C.text2,
                      fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700,
                      display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                    }}>
                      {i + 1}
                    </span>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 13.5, color: C.text, fontWeight: 600 }}>{opt.label}</span>
                        {opt.recommended && (
                          <span style={{
                            fontSize: 9.5, fontWeight: 700, color: C.sage,
                            background: C.sageDim, border: `1px solid ${C.sageRing}`,
                            borderRadius: 999, padding: "1px 7px",
                            letterSpacing: "0.06em", textTransform: "uppercase",
                          }}>
                            Production
                          </span>
                        )}
                      </div>
                      <p style={{ fontSize: 12, color: C.text2, marginTop: 3, lineHeight: 1.4 }}>{opt.desc}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          {/* Generation */}
          <section style={{ marginBottom: 22 }}>
            <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: C.text3, marginBottom: 10 }}>
              Generation variant (1–5)
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {GO.map((opt, i) => {
                const active = pipeline.generation === opt.value;
                return (
                  <button
                    key={opt.value}
                    onClick={() => onChange({ ...pipeline, generation: opt.value, generationShort: opt.short })}
                    style={{
                      textAlign: "left", display: "flex", alignItems: "flex-start", gap: 12,
                      padding: "10px 12px", borderRadius: 9,
                      border: `1px solid ${active ? C.sage : C.border}`,
                      background: active ? C.sageDim : C.surface,
                      cursor: "pointer", transition: "all 140ms ease",
                    }}
                  >
                    <span style={{
                      width: 22, height: 22, borderRadius: 999,
                      background: active ? C.sage : C.surface2,
                      color: active ? "#fff" : C.text2,
                      fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700,
                      display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                    }}>
                      {i + 1}
                    </span>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 13.5, color: C.text, fontWeight: 600 }}>{opt.label}</span>
                        {opt.recommended && (
                          <span style={{
                            fontSize: 9.5, fontWeight: 700, color: C.sage,
                            background: C.sageDim, border: `1px solid ${C.sageRing}`,
                            borderRadius: 999, padding: "1px 7px",
                            letterSpacing: "0.06em", textTransform: "uppercase",
                          }}>
                            Production
                          </span>
                        )}
                      </div>
                      <p style={{ fontSize: 12, color: C.text2, marginTop: 3, lineHeight: 1.4 }}>{opt.desc}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          {/* Verification toggle */}
          <section style={{ marginBottom: 22 }}>
            <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: C.text3, marginBottom: 10 }}>
              Verification
            </p>
            <label style={{
              display: "flex", alignItems: "center", gap: 14,
              padding: "12px 14px", borderRadius: 10,
              border: `1px solid ${C.border}`, background: C.surface, cursor: "pointer",
            }}>
              <div style={{ flex: 1 }}>
                <p style={{ fontSize: 13.5, fontWeight: 600, color: C.text }}>
                  Dual fidelity verification
                </p>
                <p style={{ fontSize: 12, color: C.text2, marginTop: 3, lineHeight: 1.4 }}>
                  NLI entailment + LLM-as-judge. Adds ~600ms latency.
                </p>
              </div>
              <Toggle checked={pipeline.verify} onChange={v => onChange({ ...pipeline, verify: v })} />
            </label>
          </section>

          {/* Top-k slider */}
          <section>
            <p style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", textTransform: "uppercase", color: C.text3, marginBottom: 10 }}>
              Top-k evidence
            </p>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: C.text2 }}>retrieve top</span>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 13, color: C.sage, fontWeight: 600 }}>
                  {pipeline.k}
                </span>
              </div>
              <input
                type="range"
                value={pipeline.k}
                onChange={e => onChange({ ...pipeline, k: parseInt(e.target.value, 10) })}
                min={1} max={10}
                style={{ width: "100%", accentColor: C.sage }}
              />
              <div style={{
                display: "flex", justifyContent: "space-between", marginTop: 3,
                fontSize: 10, color: C.text3, fontFamily: "var(--font-mono)",
              }}>
                <span>1</span><span>10</span>
              </div>
            </div>
          </section>
        </div>

        {/* Footer */}
        <div style={{
          flexShrink: 0, padding: "14px 22px",
          borderTop: `1px solid ${C.border}`, background: C.surface2,
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <span style={{ fontSize: 11, color: C.text3, fontFamily: "var(--font-mono)" }}>
            POST /api/v1/simplify
          </span>
          <button
            onClick={onClose}
            style={{
              padding: "8px 16px", borderRadius: 9,
              border: `1px solid ${C.sage}`, background: C.sage,
              color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer",
            }}
          >
            Done
          </button>
        </div>
      </div>
    </>
  );
}
