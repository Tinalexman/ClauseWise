/**
 * Design tokens for the ClauseWise UI.
 *
 * The CSS custom properties live in app/globals.css (single source of truth for
 * theming). This module mirrors the same palette as JS constants so inline
 * styles can reference them without `var(--...)` lookups.
 */

export const C = {
  bg:        "#FAF7F2",
  surface:   "#FFFFFF",
  surface2:  "#F5F1EA",
  surface3:  "#EFEAE0",
  surface4:  "#E7E1D4",

  border:    "#EAE4D8",
  borderMid: "#D8D1C2",
  borderHi:  "#BFB8A8",

  text:      "#2A2622",
  text2:     "#6B655C",
  text3:     "#A39C8E",
  text4:     "#C7C0B2",

  sage:      "#4F8B6E",
  sageHi:    "#5FA081",
  sageLo:    "#3F7A5E",
  sageDim:   "rgba(79,139,110,0.10)",
  sageDimer: "rgba(79,139,110,0.05)",
  sageRing:  "rgba(79,139,110,0.22)",

  clay:      "#C97B5A",
  clayDim:   "rgba(201,123,90,0.10)",
  clayRing:  "rgba(201,123,90,0.22)",

  amber:     "#C9963C",
  amberDim:  "rgba(201,150,60,0.10)",
  amberRing: "rgba(201,150,60,0.22)",

  red:       "#B14747",
  redDim:    "rgba(177,71,71,0.10)",
  redRing:   "rgba(177,71,71,0.22)",

  blue:      "#3D6FA8",
  blueDim:   "rgba(61,111,168,0.10)",
  blueRing:  "rgba(61,111,168,0.22)",
} as const;

/**
 * Per-clause-type accent hue used in the clause sidebar.
 * Keys match the 10 consumer-relevant clause types in the ontology.
 * `unknown` is the fallback for unclassified or pasted clauses.
 */
export const TYPE_HUE: Record<string, string> = {
  indemnity:            "#B14747",
  termination:          "#C97B5A",
  confidentiality:      "#3D6FA8",
  auto_renewal:         "#C9963C",
  liability_limitation: "#8B5A9A",
  payment_terms:        "#4F8B6E",
  dispute_resolution:   "#6B655C",
  data_sharing:         "#3D8FA8",
  non_compete:          "#A8763D",
  refund_policy:        "#5FA081",
  unknown:              "#A39C8E",
};

/**
 * Severity styling for the 4-level risk scale used by RiskPanel and
 * InsightsRail. Each entry carries the label plus four coordinated colors
 * (dot · bg · ring · text) so callers don't have to reach back into `C`.
 */
export const SEVERITY = {
  critical: { label: "Critical", dot: C.red,   bg: C.redDim,   ring: C.redRing,   text: C.red   },
  high:     { label: "High",     dot: C.clay,  bg: C.clayDim,  ring: C.clayRing,  text: C.clay  },
  medium:   { label: "Medium",   dot: C.amber, bg: C.amberDim, ring: C.amberRing, text: C.amber },
  low:      { label: "Low",      dot: C.sage,  bg: C.sageDim,  ring: C.sageRing,  text: C.sage  },
} as const;

export type Severity = keyof typeof SEVERITY;


