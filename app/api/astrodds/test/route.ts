import { NextResponse } from "next/server";

import { mlbScheduleUrl } from "@/lib/astrodss/sports-data/mlb";
import { matchMlbMarketToGame } from "@/lib/astrodss/sports-data/mlb-teams";
import { inferBetType, safeNumber } from "@/lib/astrodss/sports-data/normalize";
import { getMlbMarketRejectionReason, normalizePolymarketEvents, polymarketEventsUrl, polymarketSportQueryTerms } from "@/lib/astrodss/sports-data/polymarket";
import type { AstroddsApiTestResult, AstroddsApiTestSource, AstroddsDiagnosticStatus } from "@/lib/astrodss/sports-data/types";
import { openMeteoForecastUrl } from "@/lib/astrodss/sports-data/weather";

export const dynamic = "force-dynamic";

type GammaEvent = {
  title?: string;
  category?: string;
  markets?: Array<{
    question?: string;
    title?: string;
    category?: string;
  }>;
};

type MlbScheduleResponse = {
  dates?: Array<{
    games?: Array<{
      gameDate?: string;
      teams?: {
        away?: {
          team?: { name?: string };
          probablePitcher?: { fullName?: string };
        };
        home?: {
          team?: { name?: string };
          probablePitcher?: { fullName?: string };
        };
      };
      venue?: { name?: string };
    }>;
  }>;
};

type OpenMeteoTestResponse = {
  current?: {
    temperature_2m?: number;
    precipitation?: number;
    wind_speed_10m?: number;
  };
  hourly?: {
    temperature_2m?: number[];
    precipitation_probability?: number[];
    wind_speed_10m?: number[];
  };
};

const VALID_SOURCES = new Set<AstroddsApiTestSource>(["polymarket", "mlb", "weather", "matching"]);

function testedAt() {
  return new Date().toISOString();
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unknown API test failure";
}

function httpStatusFrom(statuses: number[]) {
  if (!statuses.length) return undefined;
  return statuses.find((status) => status < 200 || status >= 300) ?? statuses[0];
}

function result(source: AstroddsApiTestSource, payload: Omit<AstroddsApiTestResult, "source" | "testedAt">): AstroddsApiTestResult {
  return {
    source,
    testedAt: testedAt(),
    ...payload,
  };
}

async function testPolymarket(): Promise<AstroddsApiTestResult> {
  const source = "polymarket";
  const terms = polymarketSportQueryTerms("MLB");
  const urls = terms.map((term) => polymarketEventsUrl(term));
  const settled = await Promise.allSettled(
    urls.map(async (url) => {
      const response = await fetch(url, {
        cache: "no-store",
        headers: { accept: "application/json" },
      });

      if (!response.ok) throw new Error(`Polymarket Gamma API returned ${response.status} for ${url.toString()}`);
      const data = (await response.json()) as unknown;
      return {
        httpStatus: response.status,
        url: url.toString(),
        events: Array.isArray(data) ? (data as GammaEvent[]) : [],
      };
    }),
  );

  const successes = settled.flatMap((entry) => (entry.status === "fulfilled" ? [entry.value] : []));
  const errors = settled.flatMap((entry) => (entry.status === "rejected" ? [errorMessage(entry.reason)] : []));
  const normalized = normalizePolymarketEvents(successes.flatMap((entry) => entry.events), "MLB");

  if (!successes.length) {
    return result(source, {
      status: "FAILED",
      sourceUrl: urls.map(String).join(" | "),
      count: 0,
      error: errors.join(" | ") || "Polymarket Gamma API did not return any successful responses.",
    });
  }

  const status: AstroddsDiagnosticStatus = errors.length || !normalized.acceptedRawMarkets.length ? "PARTIAL" : "CONNECTED_SERVER";

  return result(source, {
    status,
    sourceUrl: urls.map(String).join(" | "),
    httpStatus: httpStatusFrom(successes.map((entry) => entry.httpStatus)),
    count: normalized.rawMarketsFetched,
    sample: {
      rawEventsFetched: normalized.rawEventsFetched,
      rawMarketsFetched: normalized.rawMarketsFetched,
      rejectedNonMlbMarkets: normalized.rejectedMarkets.length,
      mlbMarketsDetected: normalized.acceptedRawMarkets.length,
      sampleMarketTitle: normalized.acceptedRawMarkets[0]?.title ?? normalized.rejectedMarkets[0]?.title,
      rejectedSample: normalized.rejectedMarkets[0]
        ? {
            title: normalized.rejectedMarkets[0].title,
            rejectedReason: normalized.rejectedMarkets[0].rejectedReason ?? "Not MLB / no team match",
          }
        : undefined,
      httpStatuses: successes.map((entry) => ({ url: entry.url, status: entry.httpStatus })),
    },
    error: errors.length ? errors.join(" | ") : !normalized.acceptedRawMarkets.length ? "Polymarket connected, but no MLB markets were detected in the active MLB/baseball queries." : undefined,
  });
}

async function testMlb(): Promise<AstroddsApiTestResult> {
  const source = "mlb";
  const url = mlbScheduleUrl();
  const response = await fetch(url, {
    cache: "no-store",
    headers: { accept: "application/json" },
  });

  if (!response.ok) {
    return result(source, {
      status: "FAILED",
      sourceUrl: url.toString(),
      httpStatus: response.status,
      count: 0,
      error: `MLB StatsAPI returned ${response.status}`,
    });
  }

  const data = (await response.json()) as MlbScheduleResponse;
  const games = data.dates?.flatMap((day) => day.games ?? []) ?? [];
  const probablePitchersFound = games.filter((game) => game.teams?.away?.probablePitcher?.fullName || game.teams?.home?.probablePitcher?.fullName).length;
  const venuesFound = games.filter((game) => game.venue?.name).length;
  const missingPitchers = games.length - probablePitchersFound;
  const status: AstroddsDiagnosticStatus = games.length === 0 || missingPitchers > 0 ? "PARTIAL" : "CONNECTED_SERVER";
  const sampleGame = games[0];

  return result(source, {
    status,
    sourceUrl: url.toString(),
    httpStatus: response.status,
    count: games.length,
    sample: {
      gamesFetched: games.length,
      venuesFound,
      probablePitchersFound,
      sampleGame: sampleGame
        ? {
            game: `${sampleGame.teams?.away?.team?.name ?? "Away"} vs ${sampleGame.teams?.home?.team?.name ?? "Home"}`,
            startTime: sampleGame.gameDate,
            venue: sampleGame.venue?.name,
            probablePitchers: {
              away: sampleGame.teams?.away?.probablePitcher?.fullName ?? "TBD",
              home: sampleGame.teams?.home?.probablePitcher?.fullName ?? "TBD",
            },
          }
        : undefined,
    },
    error:
      games.length === 0
        ? "MLB StatsAPI connected, but no games returned for today plus the next few days."
        : missingPitchers > 0
          ? `Probable pitchers missing for ${missingPitchers} game${missingPitchers === 1 ? "" : "s"}.`
          : undefined,
  });
}

function fahrenheitFromCelsius(value?: number) {
  return typeof value === "number" ? Math.round((value * 9) / 5 + 32) : undefined;
}

function mphFromKmh(value?: number) {
  return typeof value === "number" ? Math.round(value * 0.621371) : undefined;
}

async function testWeather(): Promise<AstroddsApiTestResult> {
  const source = "weather";
  const url = openMeteoForecastUrl({
    latitude: 34.0739,
    longitude: -118.24,
    sport: "MLB",
  });
  const response = await fetch(url, {
    cache: "no-store",
    headers: { accept: "application/json" },
  });

  if (!response.ok) {
    return result(source, {
      status: "FAILED",
      sourceUrl: url.toString(),
      httpStatus: response.status,
      count: 0,
      error: `Open-Meteo returned ${response.status}`,
    });
  }

  const data = (await response.json()) as OpenMeteoTestResponse;
  const temperatureF = fahrenheitFromCelsius(safeNumber(data.current?.temperature_2m) ?? safeNumber(data.hourly?.temperature_2m?.[0]));
  const windMph = mphFromKmh(safeNumber(data.current?.wind_speed_10m) ?? safeNumber(data.hourly?.wind_speed_10m?.[0]));
  const precipitation = safeNumber(data.current?.precipitation) ?? safeNumber(data.hourly?.precipitation_probability?.[0]);
  const weatherFetched = typeof temperatureF === "number" || typeof windMph === "number" || typeof precipitation === "number";

  return result(source, {
    status: weatherFetched ? "CONNECTED_SERVER" : "PARTIAL",
    sourceUrl: url.toString(),
    httpStatus: response.status,
    count: weatherFetched ? 1 : 0,
    sample: {
      testLocation: "Los Angeles / Dodger Stadium area",
      weatherFetched,
      temperatureF,
      windMph,
      precipitation,
      venueMapping: "Known test coordinates supplied directly",
    },
    error: weatherFetched ? undefined : "Open-Meteo connected, but the response did not include usable temperature, wind, or precipitation fields.",
  });
}

function testMatching(): AstroddsApiTestResult {
  const source = "matching";
  const positiveCases = [
    {
      awayTeam: "Toronto Blue Jays",
      homeTeam: "Atlanta Braves",
      game: "Toronto Blue Jays vs Atlanta Braves",
      marketTitle: "Toronto Blue Jays vs Atlanta Braves",
    },
    {
      awayTeam: "Kansas City Royals",
      homeTeam: "Cincinnati Reds",
      game: "Kansas City Royals vs Cincinnati Reds",
      marketTitle: "Kansas City Royals vs Cincinnati Reds",
    },
    {
      awayTeam: "Detroit Tigers",
      homeTeam: "Chicago White Sox",
      game: "Detroit Tigers vs Chicago White Sox",
      marketTitle: "Detroit Tigers vs Chicago White Sox",
    },
    {
      awayTeam: "Colorado Rockies",
      homeTeam: "Los Angeles Dodgers",
      game: "Colorado Rockies vs Los Angeles Dodgers",
      marketTitle: "Colorado Rockies vs Los Angeles Dodgers",
    },
    {
      awayTeam: "Colorado Rockies",
      homeTeam: "Los Angeles Dodgers",
      game: "Colorado Rockies vs Los Angeles Dodgers",
      marketTitle: "Los Angeles Dodgers vs Colorado Rockies: O/U 7.5",
    },
  ];
  const falsePositiveCases = [
    "2026 NHL Stanley Cup Champion - Will the Detroit Red Wings win?",
    "2026 NHL Stanley Cup Champion - Will the Toronto Maple Leafs win?",
    "2026 NBA Champion - Will the Toronto Raptors win?",
    "2026 NBA Finals - Will the Los Angeles Clippers win?",
    "MicroStrategy sells any Bitcoin in 2025?",
    "Who will win the World Series in 2026?",
  ];
  const positiveTests = positiveCases.map((sample) => {
    const marketTitle = sample.marketTitle;
    const betType = inferBetType(marketTitle);
    const marketOutcomes =
      betType === "SPREAD" || betType === "MONEYLINE"
        ? [sample.homeTeam]
        : betType === "TOTAL"
          ? ["Over", "Under"]
          : [sample.awayTeam, sample.homeTeam];
    const match = matchMlbMarketToGame({
      ...sample,
      marketTitle,
      marketPick: betType === "TOTAL" ? "Over 7.5" : sample.homeTeam,
      marketOutcomes,
      betType,
    });

    return {
      marketTitle,
      matched: match.matched,
      matchedTeams: match.matched ? [sample.awayTeam, sample.homeTeam] : [],
      inferredBetType: betType,
      matchReason: match.reason,
      unmatchedReason: match.unmatchedReason || undefined,
      score: match.score,
    };
  });
  const rejectionTests = falsePositiveCases.map((marketTitle) => {
    const rejectedReason = getMlbMarketRejectionReason(marketTitle);

    return {
      marketTitle,
      rejected: Boolean(rejectedReason),
      rejectedReason: rejectedReason ?? "Not rejected",
    };
  });
  const matchedCount = positiveTests.filter((entry) => entry.matched).length;
  const rejectedCount = rejectionTests.filter((entry) => entry.rejected).length;
  const passed = matchedCount === positiveTests.length && rejectedCount === rejectionTests.length;

  return result(source, {
    status: passed ? "CONNECTED_SERVER" : matchedCount > 0 || rejectedCount > 0 ? "PARTIAL" : "FAILED",
    count: positiveTests.length + rejectionTests.length,
    sample: {
      sampleGame: "MLB alias + false-positive rejection suite",
      matchedCount,
      rejectedCount,
      positiveTests,
      rejectionTests,
    },
    error: passed
      ? undefined
      : `${positiveTests.length - matchedCount} MLB title match failure(s); ${rejectionTests.length - rejectedCount} false-positive rejection failure(s).`,
  });
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const sourceParam = (searchParams.get("source") ?? "matching").toLowerCase() as AstroddsApiTestSource;
  const source = VALID_SOURCES.has(sourceParam) ? sourceParam : "matching";

  try {
    const payload =
      source === "polymarket"
        ? await testPolymarket()
        : source === "mlb"
          ? await testMlb()
          : source === "weather"
            ? await testWeather()
            : testMatching();

    return NextResponse.json(payload, {
      headers: {
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return NextResponse.json(
      result(source, {
        status: "FAILED",
        count: 0,
        error: errorMessage(error),
      }),
      {
        status: 200,
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }
}
