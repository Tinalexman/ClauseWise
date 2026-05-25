/**
 * Typed client for the ClauseWise FastAPI backend.
 *
 * Endpoints (see src/api/main.py):
 *   POST /api/v1/upload     — multipart contract upload → clause extraction
 *   POST /api/v1/simplify   — clause text → full pipeline (retrieve · generate · verify)
 *   POST /api/v1/followup   — conversational Q&A grounded on a prior clause
 *   POST /api/v1/study/log  — fire-and-forget interaction event log
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

/* ─────────────────────────────────────────────────────────────
   Domain types
   ───────────────────────────────────────────────────────────── */

export type RetrievalConfig =
  | "bm25"
  | "dense"
  | "hybrid"
  | "hybrid_reranker"
  | "hybrid_reranker_filter";

export type GenerationVariant =
  | "extractive"
  | "vanilla"
  | "prompted"
  | "rag"
  | "proposed";

export type StudyGroup = "A" | "B" | "C" | "D";

export type ClauseType =
  | "indemnity"
  | "termination"
  | "confidentiality"
  | "auto_renewal"
  | "liability_limitation"
  | "payment_terms"
  | "dispute_resolution"
  | "data_sharing"
  | "non_compete"
  | "refund_policy"
  | "unknown";

export interface ClauseItem {
  clause_id: string;
  text: string;
  clause_type: ClauseType | string;
  source_doc: string;
  doc_type: string;
  word_count: number;
}

export interface EvidenceUsage {
  evidence_id: string;
  relevance_score: number;
}

export interface RiskDetail {
  risk_category: string;
  severity: "critical" | "high" | "medium" | "low";
  explanation: string;
  recommended_action: string;
}

export interface VerificationResult {
  fidelity_score: number;
  passed: boolean;
  entailment_label: string;
  revision_count: number;
  flags: string[];
}

export interface GenerationMetadata {
  model: string;
  temperature: number;
  latency_ms: number;
  token_count_input: number;
  token_count_output: number;
  timestamp: string;
}

export interface ExplanationOutput {
  clause_id: string;
  plain_english: string;
  user_implications: string;
  check_before_signing: string[];
  seek_legal_advice: { recommended: boolean; reason?: string };
  risks: RiskDetail[];
  evidence_used: EvidenceUsage[];
  verification: VerificationResult | null;
  confidence: "high" | "medium" | "low";
  readability: { flesch_kincaid_grade: number };
  metadata: GenerationMetadata;
}

/* ─────────────────────────────────────────────────────────────
   Pipeline option lists (drive the PipelineDrawer UI)
   ───────────────────────────────────────────────────────────── */

export interface PipelineOption<V extends string> {
  value: V;
  label: string;
  short: string;
  desc: string;
  recommended?: boolean;
}

export const RETRIEVAL_OPTIONS: PipelineOption<RetrievalConfig>[] = [
  { value: "bm25",                    label: "BM25 only",                  short: "BM25",       desc: "Sparse lexical baseline using rank_bm25." },
  { value: "dense",                   label: "Dense only",                 short: "Dense",      desc: "MiniLM-L6-v2 embeddings via FAISS." },
  { value: "hybrid",                  label: "Hybrid (BM25 + dense)",      short: "Hybrid",     desc: "Reciprocal rank fusion of sparse + dense." },
  { value: "hybrid_reranker",         label: "Hybrid + cross-encoder",     short: "Reranked",   desc: "Adds ms-marco MiniLM rerank stage." },
  { value: "hybrid_reranker_filter",  label: "Hybrid + reranker + filter", short: "Production", desc: "Plus clause-type metadata filter.", recommended: true },
];

export const GENERATION_OPTIONS: PipelineOption<GenerationVariant>[] = [
  { value: "extractive", label: "Extractive baseline", short: "Extractive", desc: "Sentence selection from the source clause only." },
  { value: "vanilla",    label: "Vanilla LLM",          short: "Vanilla",    desc: "GPT-4o-mini with no retrieval, no domain prompt." },
  { value: "prompted",   label: "Prompted LLM",         short: "Prompted",   desc: "Vanilla + plain-English prompting rubric." },
  { value: "rag",        label: "RAG",                  short: "RAG",        desc: "Prompted LLM grounded on retrieved evidence." },
  { value: "proposed",   label: "ClauseWise (full)",    short: "ClauseWise", desc: "RAG + risk ontology context + verification loop.", recommended: true },
];

/* ─────────────────────────────────────────────────────────────
   Request payloads
   ───────────────────────────────────────────────────────────── */

export interface SimplifyRequest {
  clause_text: string;
  clause_type: ClauseType;
  retrieval_config: RetrievalConfig;
  generation_variant: GenerationVariant;
  include_verification: boolean;
}

export interface FollowupRequest {
  clause_id: string;
  question: string;
  conversation_history: { role: "user" | "assistant"; content: string }[];
}

export interface LogContext {
  session_id: string;
  participant_id: string;
  group: StudyGroup;
}

/* ─────────────────────────────────────────────────────────────
   Fetch helpers
   ───────────────────────────────────────────────────────────── */

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${detail || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

/* ─────────────────────────────────────────────────────────────
   Public API surface
   ───────────────────────────────────────────────────────────── */

export const api = {
  async upload(file: File): Promise<{ clauses: ClauseItem[] }> {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_BASE}/api/v1/upload`, { method: "POST", body: form });
    if (!res.ok) {
      const detail = await res.text().catch(() => res.statusText);
      throw new Error(`${res.status} ${detail || res.statusText}`);
    }
    return res.json();
  },

  simplify(req: SimplifyRequest): Promise<{ explanation: ExplanationOutput }> {
    return postJSON("/api/v1/simplify", req);
  },

  followup(req: FollowupRequest): Promise<{ answer: string }> {
    return postJSON("/api/v1/followup", req);
  },
};



/**
 * Best-effort interaction logger. Failures are swallowed so a flaky log
 * endpoint never breaks the user-facing flow.
 */
export function logEvent(ctx: LogContext, action: string, target: string): void {
  if (typeof window === "undefined") return;
  const payload = { ...ctx, action, target, ts: Date.now() };
  try {
    const url = `${API_BASE}/api/v1/study/log`;
    const blob = new Blob([JSON.stringify(payload)], { type: "application/json" });
    if (navigator.sendBeacon?.(url, blob)) return;
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* swallow — telemetry must never crash the UI */
  }
}
