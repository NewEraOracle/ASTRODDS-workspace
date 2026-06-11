import { readFile } from "node:fs/promises";
import path from "node:path";

export const MLB_PITCHER_FEATURE_REPORT_PATH = path.join(process.cwd(), "mlb-engine", "data", "processed", "mlb_pitcher_features_report.json");

export type PitcherFeatureStatus = "available" | "partial" | "missing";

export type PitcherFeatureDataQualitySummary = {
  high: number;
  medium: number;
  low: number;
  missing: number;
};

export type PitcherFeatureDiagnostics = {
  status: PitcherFeatureStatus;
  available: boolean;
  totalGamesRead: number;
  completedGamesUsed: number;
  gamesWithPitcherData: number;
  gamesWithFullPitcherData: number;
  gamesWithPartialPitcherData: number;
  gamesMissingPitcherData: number;
  dataQualitySummary: PitcherFeatureDataQualitySummary;
  warnings: string[];
  generatedAt?: string;
  sourcePath: string;
  enhancedMoneylineCsv?: string;
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

function safeDefault(sourcePath = MLB_PITCHER_FEATURE_REPORT_PATH, warning?: string): PitcherFeatureDiagnostics {
  return {
    status: "missing",
    available: false,
    totalGamesRead: 0,
    completedGamesUsed: 0,
    gamesWithPitcherData: 0,
    gamesWithFullPitcherData: 0,
    gamesWithPartialPitcherData: 0,
    gamesMissingPitcherData: 0,
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

function normalizeStatus(summary: PitcherFeatureDiagnostics): PitcherFeatureDiagnostics {
  if (summary.gamesWithPitcherData > 0 && summary.gamesMissingPitcherData > 0) {
    return {
      ...summary,
      status: "partial",
      available: true,
    };
  }
  if (summary.gamesWithPitcherData > 0) {
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

function normalizeDiagnostics(raw: unknown, sourcePath: string): PitcherFeatureDiagnostics {
  if (!isRecord(raw)) {
    return safeDefault(sourcePath, "Pitcher feature report skipped: invalid JSON shape.");
  }

  const summary: PitcherFeatureDiagnostics = {
    status: "missing",
    available: false,
    totalGamesRead: optionalNumber(raw.total_games_read) ?? 0,
    completedGamesUsed: optionalNumber(raw.completed_games_used) ?? optionalNumber(raw.output_row_count) ?? 0,
    gamesWithPitcherData: optionalNumber(raw.games_with_pitcher_data) ?? 0,
    gamesWithFullPitcherData: optionalNumber(raw.games_with_full_pitcher_data) ?? 0,
    gamesWithPartialPitcherData: optionalNumber(raw.games_with_partial_pitcher_data) ?? 0,
    gamesMissingPitcherData: optionalNumber(raw.games_missing_pitcher_data) ?? 0,
    dataQualitySummary: {
      high: isRecord(raw.pitcher_data_quality_summary) ? optionalNumber(raw.pitcher_data_quality_summary.high) ?? 0 : 0,
      medium: isRecord(raw.pitcher_data_quality_summary) ? optionalNumber(raw.pitcher_data_quality_summary.medium) ?? 0 : 0,
      low: isRecord(raw.pitcher_data_quality_summary) ? optionalNumber(raw.pitcher_data_quality_summary.low) ?? 0 : 0,
      missing: isRecord(raw.pitcher_data_quality_summary) ? optionalNumber(raw.pitcher_data_quality_summary.missing) ?? 0 : 0,
    },
    warnings: stringArray(raw.warnings),
    generatedAt: optionalString(raw.generated_at),
    sourcePath,
    enhancedMoneylineCsv: isRecord(raw.merged_enhanced_output) ? optionalString(raw.merged_enhanced_output.enhanced_output_csv) : undefined,
  };

  return normalizeStatus(summary);
}

export async function loadPitcherFeatureStatus(sourcePath = MLB_PITCHER_FEATURE_REPORT_PATH): Promise<PitcherFeatureDiagnostics> {
  try {
    const raw = (await readFile(sourcePath, "utf8")).replace(/^\uFEFF/, "");
    try {
      return normalizeDiagnostics(JSON.parse(raw), sourcePath);
    } catch {
      return safeDefault(sourcePath, "Pitcher feature report skipped: invalid JSON in mlb_pitcher_features_report.json.");
    }
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") {
      return safeDefault(sourcePath);
    }
    return safeDefault(sourcePath, `Pitcher feature report skipped: ${error instanceof Error ? error.message : "unknown file read error"}.`);
  }
}
