import { readFile } from "node:fs/promises";
import path from "node:path";

export const MLB_WEATHER_BALLPARK_FEATURE_REPORT_PATH = path.join(
  process.cwd(),
  "mlb-engine",
  "data",
  "processed",
  "mlb_weather_ballpark_features_report.json",
);

export type WeatherBallparkFeatureStatus = "available" | "partial" | "missing";

export type WeatherBallparkFeatureDiagnostics = {
  status: WeatherBallparkFeatureStatus;
  available: boolean;
  gamesWithVenueData: number;
  gamesWithWeatherData: number;
  gamesMissingWeatherData: number;
  gamesWithBallparkFactorData: number;
  dataQuality: "high" | "medium" | "low" | "missing";
  warnings: string[];
  generatedAt?: string;
  sourcePath: string;
  mergedEnhancedCsv?: string;
  mergedPitcherBullpenWeatherCsv?: string;
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

function safeDefault(sourcePath = MLB_WEATHER_BALLPARK_FEATURE_REPORT_PATH, warning?: string): WeatherBallparkFeatureDiagnostics {
  return {
    status: "missing",
    available: false,
    gamesWithVenueData: 0,
    gamesWithWeatherData: 0,
    gamesMissingWeatherData: 0,
    gamesWithBallparkFactorData: 0,
    dataQuality: "missing",
    warnings: warning ? [warning] : [],
    sourcePath,
  };
}

function normalizeStatus(summary: WeatherBallparkFeatureDiagnostics): WeatherBallparkFeatureDiagnostics {
  if (summary.gamesWithVenueData === 0) {
    return {
      ...summary,
      status: "missing",
      available: false,
    };
  }
  if (summary.gamesWithWeatherData > 0 && summary.gamesWithBallparkFactorData > 0) {
    return {
      ...summary,
      status: "available",
      available: true,
    };
  }
  return {
    ...summary,
    status: "partial",
    available: true,
  };
}

function normalizeDataQuality(value: unknown): WeatherBallparkFeatureDiagnostics["dataQuality"] {
  const quality = optionalString(value)?.toLowerCase();
  if (quality === "high" || quality === "medium" || quality === "low" || quality === "missing") return quality;
  return "missing";
}

function qualityFromSummary(summary: unknown): WeatherBallparkFeatureDiagnostics["dataQuality"] {
  if (!isRecord(summary)) return "missing";
  const high = optionalNumber(summary.high) ?? 0;
  const medium = optionalNumber(summary.medium) ?? 0;
  const low = optionalNumber(summary.low) ?? 0;
  if (high > 0) return "high";
  if (medium > 0) return "medium";
  if (low > 0) return "low";
  return "missing";
}

function normalizeDiagnostics(raw: unknown, sourcePath: string): WeatherBallparkFeatureDiagnostics {
  if (!isRecord(raw)) {
    return safeDefault(sourcePath, "Weather / ballpark report skipped: invalid JSON shape.");
  }

  const mergedEnhancedOutput = isRecord(raw.merged_enhanced_output) ? raw.merged_enhanced_output : {};
  const mergedPitcherBullpenWeatherOutput = isRecord(raw.merged_pitcher_bullpen_weather_output) ? raw.merged_pitcher_bullpen_weather_output : {};

  const summary: WeatherBallparkFeatureDiagnostics = {
    status: "missing",
    available: false,
    gamesWithVenueData: optionalNumber(raw.games_with_venue_data) ?? 0,
    gamesWithWeatherData: optionalNumber(raw.games_with_weather_data) ?? 0,
    gamesMissingWeatherData: optionalNumber(raw.games_missing_weather_data) ?? 0,
    gamesWithBallparkFactorData: optionalNumber(raw.games_with_ballpark_factor_data) ?? 0,
    dataQuality: qualityFromSummary(raw.data_quality_summary) ?? normalizeDataQuality(raw.dataQuality),
    warnings: stringArray(raw.warnings),
    generatedAt: optionalString(raw.generated_at),
    sourcePath,
    mergedEnhancedCsv: optionalString(mergedEnhancedOutput.enhanced_output_csv),
    mergedPitcherBullpenWeatherCsv: optionalString(mergedPitcherBullpenWeatherOutput.enhanced_output_csv),
  };

  return normalizeStatus(summary);
}

export async function loadWeatherBallparkFeatureStatus(sourcePath = MLB_WEATHER_BALLPARK_FEATURE_REPORT_PATH): Promise<WeatherBallparkFeatureDiagnostics> {
  try {
    const raw = (await readFile(sourcePath, "utf8")).replace(/^\uFEFF/, "");
    try {
      return normalizeDiagnostics(JSON.parse(raw), sourcePath);
    } catch {
      return safeDefault(sourcePath, "Weather / ballpark report skipped: invalid JSON in mlb_weather_ballpark_features_report.json.");
    }
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") {
      return safeDefault(sourcePath);
    }
    return safeDefault(sourcePath, `Weather / ballpark report skipped: ${error instanceof Error ? error.message : "unknown file read error"}.`);
  }
}
