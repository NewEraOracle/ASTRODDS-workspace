import { readFile } from "node:fs/promises";
import path from "node:path";

export const MLB_LINEUP_PLAYER_FEATURE_REPORT_PATH = path.join(
  process.cwd(),
  "mlb-engine",
  "data",
  "processed",
  "mlb_lineup_player_features_report.json",
);

export type LineupPlayerFeatureStatus = "available" | "partial" | "missing";

export type LineupPlayerFeatureDiagnostics = {
  status: LineupPlayerFeatureStatus;
  available: boolean;
  gamesWithConfirmedLineupData: number;
  gamesWithProjectedOrProxyLineupData: number;
  gamesMissingLineupData: number;
  dataQuality: "high" | "medium" | "low" | "missing";
  proxyUsed: boolean;
  warnings: string[];
  generatedAt?: string;
  sourcePath: string;
  mergedMoneylineCsv?: string;
  mergedPitcherBullpenWeatherLineupCsv?: string;
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

function normalizeDataQuality(value: unknown): LineupPlayerFeatureDiagnostics["dataQuality"] {
  const quality = optionalString(value)?.toLowerCase();
  if (quality === "high" || quality === "medium" || quality === "low" || quality === "missing") return quality;
  return "missing";
}

function safeDefault(sourcePath = MLB_LINEUP_PLAYER_FEATURE_REPORT_PATH, warning?: string): LineupPlayerFeatureDiagnostics {
  return {
    status: "missing",
    available: false,
    gamesWithConfirmedLineupData: 0,
    gamesWithProjectedOrProxyLineupData: 0,
    gamesMissingLineupData: 0,
    dataQuality: "missing",
    proxyUsed: false,
    warnings: warning ? [warning] : [],
    sourcePath,
  };
}

function normalizeStatus(summary: LineupPlayerFeatureDiagnostics): LineupPlayerFeatureDiagnostics {
  if (summary.gamesWithProjectedOrProxyLineupData > 0) {
    return {
      ...summary,
      available: true,
      status: summary.gamesMissingLineupData > 0 ? "partial" : "available",
    };
  }
  return {
    ...summary,
    status: "missing",
    available: false,
  };
}

function normalizeDiagnostics(raw: unknown, sourcePath: string): LineupPlayerFeatureDiagnostics {
  if (!isRecord(raw)) {
    return safeDefault(sourcePath, "Lineup / player report skipped: invalid JSON shape.");
  }

  const mergedMoneylineOutput = isRecord(raw.merged_moneyline_output) ? raw.merged_moneyline_output : {};
  const mergedRicherOutput = isRecord(raw.merged_pitcher_bullpen_weather_lineup_output) ? raw.merged_pitcher_bullpen_weather_lineup_output : {};

  const summary: LineupPlayerFeatureDiagnostics = {
    status: "missing",
    available: false,
    gamesWithConfirmedLineupData: optionalNumber(raw.games_with_confirmed_lineup_data) ?? 0,
    gamesWithProjectedOrProxyLineupData: optionalNumber(raw.games_with_projected_or_proxy_lineup_data) ?? 0,
    gamesMissingLineupData: optionalNumber(raw.games_missing_lineup_data) ?? 0,
    dataQuality: normalizeDataQuality(raw.lineup_data_quality),
    proxyUsed: raw.proxy_used === true,
    warnings: stringArray(raw.warnings),
    generatedAt: optionalString(raw.generated_at),
    sourcePath,
    mergedMoneylineCsv: optionalString(mergedMoneylineOutput.enhanced_output_csv),
    mergedPitcherBullpenWeatherLineupCsv: optionalString(mergedRicherOutput.enhanced_output_csv),
  };

  return normalizeStatus(summary);
}

export async function loadLineupPlayerFeatureStatus(sourcePath = MLB_LINEUP_PLAYER_FEATURE_REPORT_PATH): Promise<LineupPlayerFeatureDiagnostics> {
  try {
    const raw = (await readFile(sourcePath, "utf8")).replace(/^\uFEFF/, "");
    try {
      return normalizeDiagnostics(JSON.parse(raw), sourcePath);
    } catch {
      return safeDefault(sourcePath, "Lineup / player report skipped: invalid JSON in mlb_lineup_player_features_report.json.");
    }
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") {
      return safeDefault(sourcePath);
    }
    return safeDefault(sourcePath, `Lineup / player report skipped: ${error instanceof Error ? error.message : "unknown file read error"}.`);
  }
}
