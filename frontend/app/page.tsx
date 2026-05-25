"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { api, logEvent, ClauseItem, ExplanationOutput, RETRIEVAL_OPTIONS, GENERATION_OPTIONS } from "@/lib/api";
import type { RetrievalConfig, GenerationVariant, StudyGroup } from "@/lib/api";
import { C } from "@/lib/tokens";
import Icon, { Logo } from "@/components/clausewise/Icon";
import ClausePanel from "@/components/clausewise/ClausePanel";
import ExplanationPanel from "@/components/clausewise/ExplanationPanel";
import RiskPanel from "@/components/clausewise/RiskPanel";
import EvidencePanel from "@/components/clausewise/EvidencePanel";
import ComparisonView from "@/components/clausewise/ComparisonView";
import FollowUpPanel from "@/components/clausewise/FollowUpPanel";
import VerificationPanel from "@/components/clausewise/VerificationPanel";
import InsightsRail from "@/components/clausewise/InsightsRail";
import PipelineDrawer from "@/components/clausewise/PipelineDrawer";
import PasteModal from "@/components/clausewise/PasteModal";
import StudyControls, { getPanelVisibility } from "@/components/clausewise/StudyControls";

interface PipelineState {
  retrieval: RetrievalConfig;
  retrievalShort: string;
  generation: GenerationVariant;
  generationShort: string;
  verify: boolean;
  k: number;
}

type ActiveTab = "explanation" | "risks" | "evidence" | "comparison" | "followup" | "verification";

export default function Home() {
  const [clauses, setClauses] = useState<ClauseItem[]>([]);
  const [contractName, setContractName] = useState<string | null>(null);
  const [sessionId] = useState(() => `sess_${Math.random().toString(36).slice(2, 10)}`);
  const [selectedClause, setSelectedClause] = useState<ClauseItem | null>(null);
  const [explanation, setExplanation] = useState<ExplanationOutput | null>(null);
  const [studyGroup, setStudyGroup] = useState<StudyGroup>("D");
  const [activeTab, setActiveTab] = useState<ActiveTab>("explanation");
  const [uploadLoading, setUploadLoading] = useState(false);
  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pipeline, setPipeline] = useState<PipelineState>({
    retrieval: "hybrid_reranker_filter",
    retrievalShort: "Production",
    generation: "proposed",
    generationShort: "ClauseWise",
    verify: true,
    k: 5,
  });

  const fileRef = useRef<HTMLInputElement>(null);
  const dragCounter = useRef(0);
  const logCtx = { session_id: sessionId, participant_id: "anonymous", group: studyGroup };

  const visibility = getPanelVisibility(studyGroup);

  /* ── File processing ── */
  const processFile = useCallback(async (file: File) => {
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (![".pdf", ".docx", ".txt", ".md"].includes(ext)) {
      setUploadError("Unsupported file type — use PDF, DOCX, or TXT.");
      return;
    }
    setUploadLoading(true);
    setUploadError(null);
    setClauses([]);
    setSelectedClause(null);
    setExplanation(null);
    setContractName(file.name.replace(/\.[^.]+$/, ""));
    logEvent(logCtx, "upload", file.name);
    try {
      const res = await api.upload(file);
      setClauses(res.clauses as ClauseItem[]);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploadLoading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [studyGroup]);

  /* ── Window drag-and-drop ── */
  useEffect(() => {
    const enter = (e: DragEvent) => {
      e.preventDefault();
      dragCounter.current++;
      if (e.dataTransfer?.types.includes("Files")) setIsDragging(true);
    };
    const leave = () => {
      dragCounter.current--;
      if (dragCounter.current <= 0) { dragCounter.current = 0; setIsDragging(false); }
    };
    const over = (e: DragEvent) => e.preventDefault();
    const drop = (e: DragEvent) => {
      e.preventDefault();
      dragCounter.current = 0;
      setIsDragging(false);
      const file = e.dataTransfer?.files[0];
      if (file) processFile(file);
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", over);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("dragover", over);
      window.removeEventListener("drop", drop);
    };
  }, [processFile]);

  async function handleClauseSelect(clause: ClauseItem) {
    setSelectedClause(clause);
    setExplanation(null);
    setAnalyzeError(null);
    setActiveTab(visibility.showExplanation ? "explanation" : "comparison");
    setAnalyzeLoading(true);
    logEvent(logCtx, "click", `clause:${clause.clause_id}`);
    try {
      const res = await api.simplify({
        clause_text: clause.text,
        clause_type: clause.clause_type as never,
        retrieval_config: pipeline.retrieval,
        generation_variant: pipeline.generation,
        include_verification: pipeline.verify,
      });
      setExplanation(res.explanation);
      logEvent(logCtx, "answer_viewed", `clause:${clause.clause_id}`);
    } catch (err) {
      setAnalyzeError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzeLoading(false);
    }
  }

  function handlePasteSubmit(text: string) {
    const synthetic: ClauseItem = {
      clause_id: `paste_${Date.now()}`,
      text,
      clause_type: "unknown",
      source_doc: "pasted_text",
      doc_type: "service",
      word_count: text.split(/\s+/).filter(Boolean).length,
    };
    setClauses([synthetic]);
    setContractName("Pasted clause");
    setSelectedClause(null);
    setExplanation(null);
    setPasteOpen(false);
    handleClauseSelect(synthetic);
  }

  const allTabs: { id: ActiveTab; label: string; visible: boolean }[] = [
    { id: "explanation",   label: "Explanation",  visible: visibility.showExplanation },
    { id: "risks",         label: explanation ? `Risks · ${explanation.risks.length}` : "Risks", visible: visibility.showRisks },
    { id: "evidence",      label: "Evidence",     visible: visibility.showEvidence },
    { id: "comparison",    label: "Compare",      visible: visibility.showComparison },
    { id: "followup",      label: "Ask",          visible: visibility.showFollowUp },
    { id: "verification",  label: "Verify",       visible: visibility.showVerification },
  ];
  const tabs = allTabs.filter(t => t.visible);

  return (
    <div style={{ height: "100dvh", display: "flex", flexDirection: "column", background: C.bg, overflow: "hidden" }}>

      {/* ── Drag overlay ── */}
      {isDragging && (
        <div className="drag-overlay">
          <div style={{
            display: "flex", flexDirection: "column", alignItems: "center", gap: 16,
            padding: "52px 72px", borderRadius: 20,
            background: C.surface, boxShadow: "0 32px 80px rgba(20,18,15,0.18)",
            border: `2px dashed ${C.sage}`,
          }}>
            <Icon name="upload" size={40} color={C.sage} />
            <div style={{ textAlign: "center" }}>
              <p style={{ fontFamily: "var(--font-display)", fontSize: 26, fontWeight: 500, color: C.text, letterSpacing: "-0.01em" }}>
                Drop your contract
              </p>
              <p style={{ fontSize: 13, color: C.text2, marginTop: 4 }}>PDF · DOCX · TXT · MD</p>
            </div>
          </div>
        </div>
      )}

      {/* ── Header ── */}
      <header style={{
        flexShrink: 0, height: 56,
        background: C.surface, borderBottom: `1px solid ${C.border}`,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 20px",
      }}>
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Logo size={30} />
          <div>
            <span style={{
              fontFamily: "var(--font-display)", fontSize: 19, fontWeight: 500,
              color: C.text, letterSpacing: "-0.015em",
            }}>
              ClauseWise
            </span>
            <span style={{
              marginLeft: 8, fontSize: 10.5, color: C.text3,
              fontWeight: 400, letterSpacing: "0.04em", textTransform: "uppercase",
            }}>
              Legal Clarity Engine
            </span>
          </div>
        </div>

        {/* Right controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {/* Pipeline chip */}
          <button
            onClick={() => setDrawerOpen(true)}
            style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "5px 11px", borderRadius: 8,
              border: `1px solid ${C.border}`, background: C.surface2,
              color: C.text2, fontSize: 11.5, fontWeight: 500, cursor: "pointer",
              transition: "all 130ms ease",
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = C.sage; e.currentTarget.style.color = C.sage; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = C.border; e.currentTarget.style.color = C.text2; }}
          >
            <Icon name="layers" size={12} color="currentColor" />
            {pipeline.retrievalShort} · {pipeline.generationShort}
            <Icon name="chevDown" size={11} color="currentColor" />
          </button>

          {/* Upload loading */}
          {uploadLoading && (
            <div style={{
              display: "flex", alignItems: "center", gap: 5,
              padding: "5px 10px", borderRadius: 8,
              background: C.sageDim, border: `1px solid ${C.sageRing}`,
            }}>
              <span className="spinner" style={{ width: 10, height: 10 }} />
              <span style={{ fontSize: 11, color: C.sage, fontWeight: 500 }}>Processing…</span>
            </div>
          )}

          {/* Paste button */}
          <button
            onClick={() => setPasteOpen(true)}
            style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "7px 13px", borderRadius: 9,
              border: `1px solid ${C.borderMid}`, background: C.surface,
              color: C.text2, fontSize: 13, fontWeight: 500, cursor: "pointer",
              transition: "all 130ms ease",
            }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = C.sage; e.currentTarget.style.color = C.sage; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = C.borderMid; e.currentTarget.style.color = C.text2; }}
          >
            <Icon name="plus" size={13} color="currentColor" />
            Paste clause
          </button>

          {/* Upload button */}
          <label style={{ cursor: "pointer" }}>
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={e => { const f = e.target.files?.[0]; if (f) processFile(f); }}
              style={{ display: "none" }}
            />
            <span style={{
              display: "inline-flex", alignItems: "center", gap: 7,
              padding: "7px 14px", borderRadius: 9,
              border: `1px solid ${C.sage}`, background: C.sage,
              color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer",
              transition: "all 130ms ease",
            }}>
              <Icon name="upload" size={13} color="#fff" />
              Upload contract
            </span>
          </label>
        </div>
      </header>

      {/* ── Study bar ── */}
      <StudyControls group={studyGroup} onChange={setStudyGroup} sessionId={sessionId} />

      {/* ── Upload error banner ── */}
      {uploadError && (
        <div style={{
          flexShrink: 0, display: "flex", alignItems: "center", gap: 8,
          padding: "8px 20px", fontSize: 13, color: C.clay,
          background: C.clayDim, borderBottom: `1px solid ${C.clayRing}`,
        }}>
          <Icon name="alert" size={14} color={C.clay} />
          {uploadError}
          <button
            onClick={() => setUploadError(null)}
            style={{ marginLeft: "auto", background: "none", border: "none", color: C.text3, cursor: "pointer", fontSize: 12 }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* ── Body: 3-column layout ── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* Column 1: Clause list (290px) */}
        <div style={{ width: 290, flexShrink: 0, borderRight: `1px solid ${C.border}`, display: "flex", flexDirection: "column" }}>
          <ClausePanel
            clauses={clauses}
            selected={selectedClause}
            onSelect={handleClauseSelect}
            contractName={contractName ?? undefined}
            loading={uploadLoading}
          />
        </div>

        {/* Column 2: Main content */}
        <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", background: C.bg }}>
          {selectedClause ? (
            <>
              {/* Clause header strip */}
              <div style={{
                flexShrink: 0, padding: "12px 24px",
                borderBottom: `1px solid ${C.border}`, background: C.surface,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                  <span style={{
                    fontSize: 9.5, fontWeight: 700, letterSpacing: "0.1em",
                    textTransform: "uppercase", color: C.sage,
                    background: C.sageDim, border: `1px solid ${C.sageRing}`,
                    borderRadius: 999, padding: "2px 9px",
                  }}>
                    {selectedClause.clause_type.replace(/_/g, " ")}
                  </span>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: 10.5, color: C.text3 }}>
                    {selectedClause.word_count} words
                  </span>
                  {analyzeLoading && (
                    <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: C.sage }}>
                      <span className="spinner" style={{ width: 10, height: 10 }} />
                      Analysing…
                    </span>
                  )}
                  {analyzeError && (
                    <span style={{ marginLeft: "auto", fontSize: 11, color: C.clay }}>
                      {analyzeError}
                    </span>
                  )}
                </div>
                <p style={{
                  fontFamily: "var(--font-display)", fontSize: 14, lineHeight: 1.65, color: C.text2,
                  display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden",
                }}>
                  {selectedClause.text}
                </p>
              </div>

              {/* Tabs */}
              {tabs.length > 0 && (
                <div style={{
                  flexShrink: 0, display: "flex", gap: 0,
                  borderBottom: `1px solid ${C.border}`, background: C.surface,
                  padding: "0 20px",
                }}>
                  {tabs.map(tab => {
                    const active = activeTab === tab.id;
                    return (
                      <button
                        key={tab.id}
                        onClick={() => {
                          setActiveTab(tab.id);
                          logEvent(logCtx, "panel_open", tab.id);
                        }}
                        style={{
                          padding: "10px 14px", fontSize: 12.5, fontWeight: active ? 600 : 400,
                          color: active ? C.sage : C.text3,
                          background: "none", border: "none",
                          borderBottom: active ? `2px solid ${C.sage}` : "2px solid transparent",
                          cursor: "pointer", marginBottom: -1,
                          transition: "color 130ms ease, border-color 130ms ease",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {tab.label}
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Active panel */}
              <div style={{ flex: 1, overflowY: "auto" }}>
                {activeTab === "explanation" && visibility.showExplanation && (
                  <ExplanationPanel explanation={explanation} loading={analyzeLoading} />
                )}
                {activeTab === "risks" && visibility.showRisks && (
                  <RiskPanel risks={explanation?.risks ?? []} loading={analyzeLoading} />
                )}
                {activeTab === "evidence" && visibility.showEvidence && (
                  <EvidencePanel evidenceUsed={explanation?.evidence_used ?? []} loading={analyzeLoading} />
                )}
                {activeTab === "comparison" && visibility.showComparison && (
                  <ComparisonView clause={selectedClause} explanation={explanation} />
                )}
                {activeTab === "followup" && visibility.showFollowUp && (
                  <FollowUpPanel clauseId={explanation?.clause_id ?? null} clauseText={selectedClause.text} />
                )}
                {activeTab === "verification" && visibility.showVerification && (
                  <VerificationPanel verification={explanation?.verification ?? null} explanation={explanation} />
                )}
              </div>
            </>
          ) : (
            <EmptyState
              uploadLoading={uploadLoading}
              onUpload={() => fileRef.current?.click()}
              onPaste={() => setPasteOpen(true)}
            />
          )}
        </main>

        {/* Column 3: Insights rail (320px) */}
        <InsightsRail
          explanation={explanation}
          pipeline={pipeline}
          onOpenConfig={() => setDrawerOpen(true)}
        />
      </div>

      {/* ── Overlays ── */}
      <PipelineDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        pipeline={pipeline}
        onChange={setPipeline}
      />
      <PasteModal
        open={pasteOpen}
        onClose={() => setPasteOpen(false)}
        onSubmit={handlePasteSubmit}
      />
    </div>
  );
}

function EmptyState({
  uploadLoading,
  onUpload,
  onPaste,
}: {
  uploadLoading: boolean;
  onUpload: () => void;
  onPaste: () => void;
}) {
  return (
    <div style={{
      flex: 1, display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      gap: 28, padding: "48px 32px",
    }}>
      <div style={{
        width: 72, height: 72, borderRadius: 20,
        background: C.surface, border: `1px solid ${C.border}`,
        display: "flex", alignItems: "center", justifyContent: "center",
        boxShadow: "0 4px 16px rgba(20,18,15,0.06)",
      }}>
        <Icon name="file" size={30} color={C.text3} />
      </div>

      <div style={{ textAlign: "center", maxWidth: 400 }}>
        <h2 style={{
          fontFamily: "var(--font-display)", fontSize: 30, fontWeight: 500,
          color: C.text, letterSpacing: "-0.02em", lineHeight: 1.25, marginBottom: 12,
        }}>
          Select a clause<br />to begin analysis
        </h2>
        <p style={{ fontSize: 14, color: C.text2, lineHeight: 1.7 }}>
          Upload a contract or paste a single clause. ClauseWise will explain it
          in plain English and surface any hidden risks.
        </p>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <button
          onClick={onUpload}
          disabled={uploadLoading}
          style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "10px 22px", borderRadius: 10,
            border: `1px solid ${C.sage}`, background: C.sage,
            color: "#fff", fontSize: 13.5, fontWeight: 600,
            cursor: uploadLoading ? "not-allowed" : "pointer",
            opacity: uploadLoading ? 0.6 : 1, transition: "all 150ms ease",
          }}
        >
          <Icon name="upload" size={14} color="#fff" />
          {uploadLoading ? "Processing…" : "Upload contract"}
        </button>
        <span style={{ fontSize: 12.5, color: C.text3 }}>or</span>
        <button
          onClick={onPaste}
          style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            padding: "10px 22px", borderRadius: 10,
            border: `1px solid ${C.borderMid}`, background: C.surface,
            color: C.text2, fontSize: 13.5, fontWeight: 500,
            cursor: "pointer", transition: "all 150ms ease",
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = C.sage; e.currentTarget.style.color = C.sage; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = C.borderMid; e.currentTarget.style.color = C.text2; }}
        >
          <Icon name="plus" size={14} color="currentColor" />
          Paste a clause
        </button>
      </div>

      <p style={{ fontSize: 12, color: C.text3 }}>
        or drag and drop a file anywhere in this window
      </p>
    </div>
  );
}
