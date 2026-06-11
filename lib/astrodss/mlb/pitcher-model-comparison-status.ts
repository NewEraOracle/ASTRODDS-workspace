import { readFile } from "node:fs/promises";
import path from "node:path";

export const MLB_PITCHER_MODEL_COMPARISON_REPORT_PATH = path.join(
  process.cwd(),
  "mlb-engine",
  "models",
  "moneyline_model_comparison_report.json",
);

export type PitcherModelComparisonRecommendation = "keep_baseline" | "candidate_pitcher_model" | "needs_more_data";

export type PitcherModelComparisonDiagnostics = {
  status: "available" | "missing" | "empty";
  recommendation: PitcherModelComparisonRecommendation;
  baselineModelVersion: string;
  baselineModelType: string;
  pitcherModelVersion: string;
  pitcherModelType: string;
  trainRows?: number;
  validationRows?: number;
  holdout2026Rows?: number;
  baselineValidationAccuracy?: number;
  baselineValidationLogLoss?: number;
  baselineValidationBrierScore?: number;
  pitcherValidationAccuracy?: number;
  pitcherValidationLogLoss?: number;
  pitcherValidationBrierScore?: number;
  baselineHoldout2026Accuracy?: number;
  baselineHoldout2026LogLoss?: number;
  baselineHoldout2026BrierScore?: number;
  pitcherHoldout2026Accuracy?: number;
  pitcherHoldout2026LogLoss?: number;
  pitcherHoldout2026BrierScore?: number;
  accuracyDelta?: number;
  logLossDelta?: number;
  brierScoreDelta?: number;
  holdoutAccuracyDelta?: number;
  holdoutLogLossDelta?: number;
  holdoutBrierScoreDelta?: number;
  featureCount?: number;
  pitcherFeatureCount?: number;
  missingPitcherFeatureRows?: number;
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

function safeDefault(sourcePath = MLB_PITCHER_MODEL_COMPARISON_REPORT_PATH, warning?: string): PitcherModelComparisonDiagnostics {
  return {
    status: "missing",
    recommendation: "needs_more_data",
    baselineModelVersion: "unknown",
    baselineModelType: "unknown",
    pitcherModelVersion: "unknown",
    pitcherModelType: "unknown",
    reasons: [],
    warnings: warning ? [warning] : [],
    sourcePath,
  };
}

function normalizeRecommendation(value: unknown): PitcherModelComparisonRecommendation {
  const recommendation = optionalString(value)?.toLowerCase();
  if (recommendation === "keep_baseline" || recommendation === "candidate_pitcher_model" || recommendation === "needs_more_data") {
    return recommendation;
  }
  return "needs_more_data";
}

function normalizeDiagnostics(raw: unknown, sourcePath: string): PitcherModelComparisonDiagnostics {
  if (!isRecord(raw)) return safeDefault(sourcePath, "Pitcher model comparison report skipped: invalid JSON shape.");

  const baseline = isRecord(raw.baseline_model) ? raw.baseline_model : {};
  const pitcher = isRecord(raw.pitcher_model) ? raw.pitcher_model : {};
  const reasons = stringArray(raw.reasons);
  const warnings = stringArray(raw.warnings);

  return {
    status: reasons.length || warnings.length || optionalString(raw.recommendation) ? "available" : "empty",
    recommendation: normalizeRecommendation(raw.recommendation),
    baselineModelVersion: optionalString(baseline.model_version) ?? "unknown",
    baselineModelType: optionalString(baseline.model_type) ?? "unknown",
    pitcherModelVersion: optionalString(pitcher.model_version) ?? "unknown",
    pitcherModelType: optionalString(pitcher.model_type) ?? "unknown",
    trainRows: optionalNumber(pitcher.train_rows),
    validationRows: optionalNumber(pitcher.validation_rows),
    holdout2026Rows: optionalNumber(pitcher.holdout_2026_rows),
    baselineValidationAccuracy: optionalNumber(baseline.validation_accuracy),
    baselineValidationLogLoss: optionalNumber(baseline.validation_log_loss),
    baselineValidationBrierScore: optionalNumber(baseline.validation_brier_score),
    pitcherValidationAccuracy: optionalNumber(pitcher.validation_accuracy),
    pitcherValidationLogLoss: optionalNumber(pitcher.validation_log_loss),
    pitcherValidationBrierScore: optionalNumber(pitcher.validation_brier_score),
    baselineHoldout2026Accuracy: optionalNumber(baseline.holdout_2026_accuracy),
    baselineHoldout2026LogLoss: optionalNumber(baseline.holdout_2026_log_loss),
    baselineHoldout2026BrierScore: optionalNumber(baseline.holdout_2026_brier_score),
    pitcherHoldout2026Accuracy: optionalNumber(pitcher.holdout_2026_accuracy),
    pitcherHoldout2026LogLoss: optionalNumber(pitcher.holdout_2026_log_loss),
    pitcherHoldout2026BrierScore: optionalNumber(pitcher.holdout_2026_brier_score),
    accuracyDelta: optionalNumber(raw.accuracy_delta),
    logLossDelta: optionalNumber(raw.log_loss_delta),
    brierScoreDelta: optionalNumber(raw.brier_score_delta),
    holdoutAccuracyDelta: optionalNumber(raw.holdout_accuracy_delta),
    holdoutLogLossDelta: optionalNumber(raw.holdout_log_loss_delta),
    holdoutBrierScoreDelta: optionalNumber(raw.holdout_brier_score_delta),
    featureCount: optionalNumber(pitcher.feature_count),
    pitcherFeatureCount: optionalNumber(pitcher.pitcher_feature_count),
    missingPitcherFeatureRows: optionalNumber(pitcher.missing_pitcher_feature_rows),
    reasons,
    warnings,
    generatedAt: optionalString(raw.generated_at),
    sourcePath,
  };
}

export async function loadPitcherModelComparisonStatus(
  sourcePath = MLB_PITCHER_MODEL_COMPARISON_REPORT_PATH,
): Promise<PitcherModelComparisonDiagnostics> {
  try {
    const raw = (await readFile(sourcePath, "utf8")).replace(/^\uFEFF/, "");
    try {
      return normalizeDiagnostics(JSON.parse(raw), sourcePath);
    } catch {
      return safeDefault(sourcePath, "Pitcher model comparison report skipped: invalid JSON in moneyline_model_comparison_report.json.");
    }
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") {
      return safeDefault(sourcePath);
    }
    return safeDefault(sourcePath, `Pitcher model comparison report skipped: ${error instanceof Error ? error.message : "unknown file read error"}.`);
  }
}
