import { readFile } from "node:fs/promises";
import path from "node:path";

export const MLB_MODERN_MODEL_COMPARISON_REPORT_PATH = path.join(
  process.cwd(),
  "mlb-engine",
  "models",
  "moneyline_modern_window_comparison_report.json",
);

export type ModernModelComparisonRecommendation =
  | "keep_current_baseline"
  | "candidate_modern_2016_2026"
  | "needs_more_data";

export type ModernModelComparisonDiagnostics = {
  status: "available" | "missing" | "empty";
  recommendation: ModernModelComparisonRecommendation;
  baselineModelVersion: string;
  baselineModelType: string;
  modernModelVersion: string;
  modernModelType: string;
  trainRows?: number;
  validationRows?: number;
  holdout2026Rows?: number;
  baselineValidationAccuracy?: number;
  baselineValidationLogLoss?: number;
  baselineValidationBrierScore?: number;
  modernValidationAccuracy?: number;
  modernValidationLogLoss?: number;
  modernValidationBrierScore?: number;
  baselineHoldout2026Accuracy?: number;
  baselineHoldout2026LogLoss?: number;
  baselineHoldout2026BrierScore?: number;
  modernHoldout2026Accuracy?: number;
  modernHoldout2026LogLoss?: number;
  modernHoldout2026BrierScore?: number;
  accuracyDelta?: number;
  logLossDelta?: number;
  brierScoreDelta?: number;
  holdoutAccuracyDelta?: number;
  holdoutLogLossDelta?: number;
  holdoutBrierScoreDelta?: number;
  featureCount?: number;
  activeModelChanged: false;
  reasons: string[];
  warnings: string[];
  generatedAt?: string;
  sourcePath: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function optionalNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0).map((item) => item.trim());
}

function safeDefault(sourcePath = MLB_MODERN_MODEL_COMPARISON_REPORT_PATH, warning?: string): ModernModelComparisonDiagnostics {
  return {
    status: "missing",
    recommendation: "needs_more_data",
    baselineModelVersion: "unknown",
    baselineModelType: "unknown",
    modernModelVersion: "unknown",
    modernModelType: "unknown",
    activeModelChanged: false,
    reasons: [],
    warnings: warning ? [warning] : [],
    sourcePath,
  };
}

function normalizeRecommendation(value: unknown): ModernModelComparisonRecommendation {
  const recommendation = optionalString(value)?.toLowerCase();
  if (
    recommendation === "keep_current_baseline" ||
    recommendation === "candidate_modern_2016_2026" ||
    recommendation === "needs_more_data"
  ) {
    return recommendation;
  }
  return "needs_more_data";
}

function normalizeDiagnostics(raw: unknown, sourcePath: string): ModernModelComparisonDiagnostics {
  if (!isRecord(raw)) return safeDefault(sourcePath, "Modern model comparison report skipped: invalid JSON shape.");

  const baseline = isRecord(raw.baseline_model) ? raw.baseline_model : {};
  const modern = isRecord(raw.modern_model) ? raw.modern_model : {};
  const reasons = stringArray(raw.reasons);
  const warnings = stringArray(raw.warnings);

  return {
    status: reasons.length || warnings.length || optionalString(raw.recommendation) ? "available" : "empty",
    recommendation: normalizeRecommendation(raw.recommendation),
    baselineModelVersion: optionalString(baseline.model_version) ?? "unknown",
    baselineModelType: optionalString(baseline.model_type) ?? "unknown",
    modernModelVersion: optionalString(modern.model_version) ?? "unknown",
    modernModelType: optionalString(modern.model_type) ?? "unknown",
    trainRows: optionalNumber(modern.train_rows),
    validationRows: optionalNumber(modern.validation_rows),
    holdout2026Rows: optionalNumber(modern.holdout_2026_rows),
    baselineValidationAccuracy: optionalNumber(baseline.validation_accuracy),
    baselineValidationLogLoss: optionalNumber(baseline.validation_log_loss),
    baselineValidationBrierScore: optionalNumber(baseline.validation_brier_score),
    modernValidationAccuracy: optionalNumber(modern.validation_accuracy),
    modernValidationLogLoss: optionalNumber(modern.validation_log_loss),
    modernValidationBrierScore: optionalNumber(modern.validation_brier_score),
    baselineHoldout2026Accuracy: optionalNumber(baseline.holdout_2026_accuracy),
    baselineHoldout2026LogLoss: optionalNumber(baseline.holdout_2026_log_loss),
    baselineHoldout2026BrierScore: optionalNumber(baseline.holdout_2026_brier_score),
    modernHoldout2026Accuracy: optionalNumber(modern.holdout_2026_accuracy),
    modernHoldout2026LogLoss: optionalNumber(modern.holdout_2026_log_loss),
    modernHoldout2026BrierScore: optionalNumber(modern.holdout_2026_brier_score),
    accuracyDelta: optionalNumber(raw.accuracy_delta),
    logLossDelta: optionalNumber(raw.log_loss_delta),
    brierScoreDelta: optionalNumber(raw.brier_score_delta),
    holdoutAccuracyDelta: optionalNumber(raw.holdout_accuracy_delta),
    holdoutLogLossDelta: optionalNumber(raw.holdout_log_loss_delta),
    holdoutBrierScoreDelta: optionalNumber(raw.holdout_brier_score_delta),
    featureCount: optionalNumber(modern.feature_count),
    activeModelChanged: false,
    reasons,
    warnings,
    generatedAt: optionalString(raw.generated_at),
    sourcePath,
  };
}

export async function loadModernModelComparisonStatus(
  sourcePath = MLB_MODERN_MODEL_COMPARISON_REPORT_PATH,
): Promise<ModernModelComparisonDiagnostics> {
  try {
    const raw = (await readFile(sourcePath, "utf8")).replace(/^\uFEFF/, "");
    try {
      return normalizeDiagnostics(JSON.parse(raw), sourcePath);
    } catch {
      return safeDefault(sourcePath, "Modern model comparison report skipped: invalid JSON in moneyline_modern_window_comparison_report.json.");
    }
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") {
      return safeDefault(sourcePath);
    }
    return safeDefault(sourcePath, `Modern model comparison report skipped: ${error instanceof Error ? error.message : "unknown file read error"}.`);
  }
}
