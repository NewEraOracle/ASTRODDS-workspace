import { readFile } from "node:fs/promises";
import path from "node:path";

export const MLB_BULLPEN_FEATURE_REPORT_PATH = path.join(
  process.cwd(),
  "mlb-engine",
  "data",
  "processed",
  "mlb_bullpen_features_report.json",
);

export type BullpenFeatureStatus = "available" | "partial" | "missing";

export type BullpenFeatureDataQualitySummary = {
  high: number;
  medium: number;
  low: number;
  missing: number;
};

export type BullpenFeatureDiagnostics = {
  status: BullpenFeatureStatus;
  available: boolean;
  totalGamesRead: number;
  completedGamesUsed: number;
  gamesWithBullpenData: number;
  gamesMissingBullpenData: number;
  gamesApproximatedBullpenData: number;
  approximationMethod: string;
  approximationUsed: boolean;
  dataQuality: "high" | "medium" | "low" | "missing";
  dataQualitySummary: BullpenFeatureDataQualitySummary;
  warnings: string[];
  generatedAt?: string;
  sourcePath: string;
  enhancedMoneylineCsv?: string;
  enhancedPitcherMoneylineCsv?: string;
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

function safeDefault(sourcePath = MLB_BULLPEN_FEATURE_REPORT_PATH, warning?: string): BullpenFeatureDiagnostics {
  return {
    status: "missing",
    available: false,
    totalGamesRead: 0,
    completedGamesUsed: 0,
    gamesWithBullpenData: 0,
    gamesMissingBullpenData: 0,
    gamesApproximatedBullpenData: 0,
    approximationMethod: "linescore innings after a starter cutoff plus recent-game stress proxy",
    approximationUsed: false,
    dataQuality: "missing",
    dataQualitySummary: {
      high: 0,
      medium: 0,
      low: 0,
      missing: 0,
    },
    warnings: warning ? [warning] : [],
    sourcePath,
  };
}

function normalizeStatus(summary: BullpenFeatureDiagnostics): BullpenFeatureDiagnostics {
  if (summary.gamesWithBullpenData > 0 && summary.gamesMissingBullpenData > 0) {
    return {
      ...summary,
      status: "partial",
      available: true,
    };
  }
  if (summary.gamesWithBullpenData > 0) {
    return {
      ...summary,
      status: "available",
      available: true,
    };
  }
  return {
    ...summary,
    status: "missing",
    available: false,
  };
}

function normalizeDataQuality(value: unknown): BullpenFeatureDiagnostics["dataQuality"] {
  const quality = optionalString(value)?.toLowerCase();
  if (quality === "high" || quality === "medium" || quality === "low" || quality === "missing") return quality;
  return "missing";
}

function normalizeDiagnostics(raw: unknown, sourcePath: string): BullpenFeatureDiagnostics {
  if (!isRecord(raw)) {
    return safeDefault(sourcePath, "Bullpen feature report skipped: invalid JSON shape.");
  }

  const mergedEnhancedOutput = isRecord(raw.merged_enhanced_output) ? raw.merged_enhanced_output : {};
  const mergedPitcherEnhancedOutput = isRecord(raw.merged_pitcher_enhanced_output) ? raw.merged_pitcher_enhanced_output : {};

  const summary: BullpenFeatureDiagnostics = {
    status: "missing",
    available: false,
    totalGamesRead: optionalNumber(raw.total_games_read) ?? 0,
    completedGamesUsed: optionalNumber(raw.completed_games_used) ?? optionalNumber(raw.output_row_count) ?? 0,
    gamesWithBullpenData: optionalNumber(raw.games_with_bullpen_data) ?? 0,
    gamesMissingBullpenData: optionalNumber(raw.games_missing_bullpen_data) ?? 0,
    gamesApproximatedBullpenData: optionalNumber(raw.games_approximated_bullpen_data) ?? optionalNumber(raw.output_row_count) ?? 0,
    approximationMethod: optionalString(raw.approximation_method) ?? "linescore innings after a starter cutoff plus recent-game stress proxy",
    approximationUsed: raw.approximation_used === true,
    dataQuality: normalizeDataQuality(raw.bullpen_data_quality),
    dataQualitySummary: {
      high: isRecord(raw.bullpen_data_quality_summary) ? optionalNumber(raw.bullpen_data_quality_summary.high) ?? 0 : 0,
      medium: isRecord(raw.bullpen_data_quality_summary) ? optionalNumber(raw.bullpen_data_quality_summary.medium) ?? 0 : 0,
      low: isRecord(raw.bullpen_data_quality_summary) ? optionalNumber(raw.bullpen_data_quality_summary.low) ?? 0 : 0,
      missing: isRecord(raw.bullpen_data_quality_summary) ? optionalNumber(raw.bullpen_data_quality_summary.missing) ?? 0 : 0,
    },
    warnings: stringArray(raw.warnings),
    generatedAt: optionalString(raw.generated_at),
    sourcePath,
    enhancedMoneylineCsv: optionalString(mergedEnhancedOutput.enhanced_output_csv),
    enhancedPitcherMoneylineCsv: optionalString(mergedPitcherEnhancedOutput.enhanced_output_csv),
  };

  return normalizeStatus(summary);
}

export async function loadBullpenFeatureStatus(sourcePath = MLB_BULLPEN_FEATURE_REPORT_PATH): Promise<BullpenFeatureDiagnostics> {
  try {
    const raw = (await readFile(sourcePath, "utf8")).replace(/^\uFEFF/, "");
    try {
      return normalizeDiagnostics(JSON.parse(raw), sourcePath);
    } catch {
      return safeDefault(sourcePath, "Bullpen feature report skipped: invalid JSON in mlb_bullpen_features_report.json.");
    }
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") {
      return safeDefault(sourcePath);
    }
    return safeDefault(sourcePath, `Bullpen feature report skipped: ${error instanceof Error ? error.message : "unknown file read error"}.`);
  }
}
