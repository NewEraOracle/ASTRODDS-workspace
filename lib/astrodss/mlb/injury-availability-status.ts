import { readFile } from "node:fs/promises";
import path from "node:path";

export const MLB_INJURY_AVAILABILITY_FEATURE_REPORT_PATH = path.join(
  process.cwd(),
  "mlb-engine",
  "data",
  "processed",
  "mlb_injury_availability_features_report.json",
);

export type InjuryAvailabilityDataQuality = "high" | "medium" | "low" | "missing";

export type InjuryAvailabilityStatus = "available" | "partial" | "missing";

export type InjuryAvailabilityDiagnostics = {
  status: InjuryAvailabilityStatus;
  available: boolean;
  gamesWithInjuryData: number;
  gamesMissingInjuryData: number;
  injurySource: string;
  dataQuality: InjuryAvailabilityDataQuality;
  warnings: string[];
  generatedAt?: string;
  sourcePath: string;
  mergedInjuriesCsv?: string;
  mergedPitcherBullpenWeatherLineupInjuriesCsv?: string;
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

function normalizeDataQuality(value: unknown): InjuryAvailabilityDataQuality {
  const quality = optionalString(value)?.toLowerCase();
  if (quality === "high" || quality === "medium" || quality === "low" || quality === "missing") return quality;
  return "missing";
}

function inferDataQuality(summary: Pick<InjuryAvailabilityDiagnostics, "available" | "gamesWithInjuryData" | "gamesMissingInjuryData">): InjuryAvailabilityDataQuality {
  if (!summary.available) return "missing";
  if (summary.gamesWithInjuryData > 0 && summary.gamesMissingInjuryData > 0) return "medium";
  if (summary.gamesWithInjuryData > 0) return "high";
  return "low";
}

function safeDefault(sourcePath = MLB_INJURY_AVAILABILITY_FEATURE_REPORT_PATH, warning?: string): InjuryAvailabilityDiagnostics {
  return {
    status: "missing",
    available: false,
    gamesWithInjuryData: 0,
    gamesMissingInjuryData: 0,
    injurySource: "unavailable",
    dataQuality: "missing",
    warnings: warning ? [warning] : [],
    sourcePath,
  };
}

function normalizeStatus(summary: InjuryAvailabilityDiagnostics): InjuryAvailabilityDiagnostics {
  if (summary.gamesWithInjuryData > 0 && summary.gamesMissingInjuryData > 0) {
    return {
      ...summary,
      status: "partial",
      available: true,
      dataQuality: summary.dataQuality === "missing" ? inferDataQuality(summary) : summary.dataQuality,
    };
  }
  if (summary.gamesWithInjuryData > 0) {
    return {
      ...summary,
      status: "available",
      available: true,
      dataQuality: summary.dataQuality === "missing" ? inferDataQuality(summary) : summary.dataQuality,
    };
  }
  return {
    ...summary,
    status: "missing",
    available: false,
    dataQuality: "missing",
  };
}

function normalizeDiagnostics(raw: unknown, sourcePath: string): InjuryAvailabilityDiagnostics {
  if (!isRecord(raw)) {
    return safeDefault(sourcePath, "Injury / availability report skipped: invalid JSON shape.");
  }

  const summary: InjuryAvailabilityDiagnostics = {
    status: "missing",
    available: false,
    gamesWithInjuryData: optionalNumber(raw.games_with_injury_data) ?? optionalNumber(raw.gamesWithInjuryData) ?? 0,
    gamesMissingInjuryData: optionalNumber(raw.games_missing_injury_data) ?? optionalNumber(raw.gamesMissingInjuryData) ?? 0,
    injurySource:
      optionalString(raw.injury_source) ??
      optionalString(raw.injurySource) ??
      "MLB StatsAPI public injured-list roster data + research-only lineup/player proxies",
    dataQuality: normalizeDataQuality(raw.injury_data_quality ?? raw.data_quality),
    warnings: stringArray(raw.warnings),
    generatedAt: optionalString(raw.generated_at) ?? optionalString(raw.generatedAt),
    sourcePath,
    mergedInjuriesCsv: optionalString(raw.merged_injuries_csv) ?? optionalString(raw.mergedInjuriesCsv),
    mergedPitcherBullpenWeatherLineupInjuriesCsv:
      optionalString(raw.merged_pitcher_bullpen_weather_lineup_injuries_csv) ??
      optionalString(raw.mergedPitcherBullpenWeatherLineupInjuriesCsv),
  };

  const normalizedWarnings = [
    ...summary.warnings,
    summary.available ? undefined : "Injury / player availability data unavailable.",
    "Public injured-list roster data is a conservative proxy; player importance is not guaranteed.",
    "Official use blocked - research only.",
  ].filter((value): value is string => Boolean(value && value.trim()));

  return normalizeStatus({
    ...summary,
    warnings: Array.from(new Set(normalizedWarnings)),
  });
}

export async function loadInjuryAvailabilityStatus(
  sourcePath = MLB_INJURY_AVAILABILITY_FEATURE_REPORT_PATH,
): Promise<InjuryAvailabilityDiagnostics> {
  try {
    const raw = (await readFile(sourcePath, "utf8")).replace(/^\uFEFF/, "");
    try {
      return normalizeDiagnostics(JSON.parse(raw), sourcePath);
    } catch {
      return safeDefault(sourcePath, "Injury / availability report skipped: invalid JSON in mlb_injury_availability_features_report.json.");
    }
  } catch (error) {
    if (error instanceof Error && "code" in error && error.code === "ENOENT") {
      return safeDefault(sourcePath);
    }
    return safeDefault(sourcePath, `Injury / availability report skipped: ${error instanceof Error ? error.message : "unknown file read error"}.`);
  }
}
