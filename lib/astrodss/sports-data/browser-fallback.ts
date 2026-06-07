import { applyDecisionEngine, rankedPicks } from "./decision-engine";
import { mlbScheduleUrl } from "./mlb";
import { describeMlbMarketTeams, matchMlbMarketToGame } from "./mlb-teams";
import { compactId, dataStatusRank, safeNumber } from "./normalize";
import { hydrateMarketsWithOrderBooks } from "./orderbook";
import {
  mlbScheduleSearchTerms,
  normalizePolymarketSources,
  polymarketEventsUrl,
  polymarketMarketsUrl,
  polymarketSportQueryTerms,
  type GammaEvent,
  type GammaMarket,
} from "./polymarket";
import type {
  AstroddsGameScan,
  AstroddsMarketScan,
  AstroddsScanDiagnostics,
  AstroddsScanResult,
  AstroddsSourceStatusMap,
} from "./types";
import { fetchWeatherContext, OPEN_METEO_FORECAST_URL } from "./weather";
import { findVenueCoordinates } from "./venues";

type MlbScheduleResponse = {
  dates?: Array<{
    games?: MlbScheduleGame[];
  }>;
  totalGames?: number;
};

type MlbScheduleGame = {
  gamePk?: number;
  gameDate?: string;
  status?: {
    abstractGameState?: string;
    detailedState?: string;
  };
  teams?: {
    away?: {
      team?: { name?: string };
      probablePitcher?: { fullName?: string };
      score?: number;
    };
    home?: {
      team?: { name?: string };
      probablePitcher?: { fullName?: string };
      score?: number;
    };
  };
  venue?: {
    name?: string;
    location?: {
      defaultCoordinates?: {
        latitude?: number | string;
        longitude?: number | string;
      };
      latitude?: number | string;
      longitude?: number | string;
    };
  };
  linescore?: {
    currentInningOrdinal?: string;
    inningState?: string;
  };
};

type BrowserPolymarketPayload = {
  markets: AstroddsMarketScan[];
  diagnostics: AstroddsScanDiagnostics["polymarket"];
  orderBookDiagnostics: AstroddsScanDiagnostics["orderBook"];
};

type BrowserMlbPayload = {
  games: AstroddsGameScan[];
  sportApi: AstroddsScanDiagnostics["sportApi"];
  weather: AstroddsScanDiagnostics["weather"];
};

const BROWSER_WARNING = "Browser fallback active because server-side fetch failed.";

function marketKey(market: AstroddsMarketScan) {
  return `${market.marketId}-${market.pick}-${market.assetId ?? ""}`;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unknown browser fallback failure";
}

function liveStatus(game: MlbScheduleGame) {
  const state = `${game.status?.abstractGameState ?? ""} ${game.status?.detailedState ?? ""}`.toLowerCase();
  if (state.includes("final")) return "FINAL" as const;
  if (state.includes("live") || state.includes("in progress")) return "LIVE" as const;
  if (state.includes("preview") || state.includes("scheduled") || state.includes("pre-game")) return "PRE_GAME" as const;
  return "UNKNOWN" as const;
}

function gameScore(game: MlbScheduleGame) {
  const away = game.teams?.away?.score;
  const home = game.teams?.home?.score;
  if (typeof away === "number" && typeof home === "number") return `${away}-${home}`;
  return "0-0";
}

function venueCoordinates(game: MlbScheduleGame) {
  const defaultCoordinates = game.venue?.location?.defaultCoordinates;
  const latitude = safeNumber(defaultCoordinates?.latitude ?? game.venue?.location?.latitude);
  const longitude = safeNumber(defaultCoordinates?.longitude ?? game.venue?.location?.longitude);

  if (typeof latitude === "number" && typeof longitude === "number") {
    return { latitude, longitude };
  }

  return findVenueCoordinates(game.venue?.name);
}

function hasProbablePitcher(game: MlbScheduleGame) {
  return Boolean(game.teams?.away?.probablePitcher?.fullName || game.teams?.home?.probablePitcher?.fullName);
}

function marketOnlyGame(market: AstroddsMarketScan): AstroddsGameScan {
  const reason = market.unmatchedReason ?? "Polymarket market found, but no matching MLB schedule game was found.";

  return {
    id: `mlb-browser-market-${compactId(market.marketTitle)}-${compactId(market.pick)}`,
    sport: "MLB",
    league: market.category ?? "MLB",
    game: market.marketTitle,
    players: market.outcomes,
    liveStatus: "UNKNOWN",
    score: "0-0",
    period: "Market only",
    weather: {
      status: "NOT_CONNECTED",
      source: "Source needed",
      impactScore: 0,
      impact: "NONE",
      summary: "NOT CONNECTED - sport schedule/venue required for weather.",
    },
    injuries: {
      status: "NOT_CONNECTED",
      source: "Source needed",
      summary: "NOT CONNECTED - MLB injury provider needed.",
    },
    lineups: {
      status: "NOT_CONNECTED",
      source: "Source needed",
      summary: "NOT CONNECTED - confirmed lineups not available from this free schedule feed.",
    },
    keyContext: [reason],
    keyPlayerStatus: "MLB Data: NOT MATCHED",
    markets: [market],
    dataStatus: "PARTIAL",
    source: "Polymarket Gamma API market-only row (browser fallback)",
    unmatchedReason: reason,
  };
}

function attachMlbMarketsToGames(
  games: AstroddsGameScan[],
  markets: AstroddsMarketScan[],
): { games: AstroddsGameScan[]; matching: AstroddsScanDiagnostics["matching"] } {
  const usedMarkets = new Set<string>();
  const unmatchedGames: string[] = [];
  const unmatchedGameReasons: Array<{ game: string; unmatchedReason: string }> = [];

  const withMarkets = games.map((game) => {
    const candidates = markets
      .map((market) => ({
        market,
        match: matchMlbMarketToGame({
          awayTeam: game.awayTeam,
          homeTeam: game.homeTeam,
          game: game.game,
          marketTitle: market.marketTitle,
          marketPick: market.pick,
          marketOutcomes: market.outcomes,
          betType: market.betType,
        }),
      }))
      .sort((a, b) => b.match.score - a.match.score);
    const matches = candidates
      .filter((candidate) => candidate.match.matched)
      .map((candidate) => ({
        ...candidate.market,
        matchReason: candidate.match.reason,
        unmatchedReason: undefined,
      }));

    matches.forEach((market) => usedMarkets.add(marketKey(market)));
    const bestUnmatchedReason =
      markets.length === 0
        ? "MLB game found, but no matching Polymarket market was found."
        : candidates[0]?.match.unmatchedReason ?? "No Polymarket markets were available for matching.";

    if (!matches.length) {
      unmatchedGames.push(game.game);
      unmatchedGameReasons.push({
        game: game.game,
        unmatchedReason: bestUnmatchedReason,
      });
    }

    return {
      ...game,
      markets: matches,
      unmatchedReason: matches.length ? undefined : bestUnmatchedReason,
    };
  });

  const unmatchedMarketRows = markets
    .filter((market) => !usedMarkets.has(marketKey(market)))
    .map((market) => {
      const detectedTeams = describeMlbMarketTeams(`${market.marketTitle} ${market.pick} ${market.outcomes.join(" ")}`);
      const unmatchedReason = games.length
        ? detectedTeams.length
          ? `Detected ${detectedTeams.join(", ")}, but no fetched MLB schedule game matched those teams.`
          : "No MLB team alias found in market title, pick, or outcomes."
        : "Polymarket market found, but no matching MLB schedule game was found.";

      return marketOnlyGame({
        ...market,
        unmatchedReason,
      });
    });
  const unmatchedMarkets = unmatchedMarketRows.map((game) => `${game.game} | ${game.markets[0]?.pick ?? "Unknown pick"}`);
  const unmatchedMarketReasons = unmatchedMarketRows.map((game) => ({
    market: `${game.game} | ${game.markets[0]?.pick ?? "Unknown pick"}`,
    unmatchedReason: game.unmatchedReason ?? "No matching game found.",
  }));
  const unmatchedReasons = [
    ...unmatchedGameReasons.map((item) => ({ type: "game" as const, name: item.game, unmatchedReason: item.unmatchedReason })),
    ...unmatchedMarketReasons.map((item) => ({ type: "market" as const, name: item.market, unmatchedReason: item.unmatchedReason })),
  ];
  const matchedGamesCount = games.length - unmatchedGames.length;
  const matchingStatus =
    games.length === 0 && markets.length === 0
      ? "NOT_CONNECTED"
      : matchedGamesCount > 0 && unmatchedGames.length === 0 && unmatchedMarkets.length === 0
        ? "CONNECTED_BROWSER"
        : "PARTIAL";

  return {
    games: [...withMarkets, ...unmatchedMarketRows],
    matching: {
      status: matchingStatus,
      sourceMode: matchingStatus === "NOT_CONNECTED" ? undefined : "BROWSER_FALLBACK",
      gamesCount: games.length,
      polymarketMarketsCount: markets.length,
      matchedMarketsCount: usedMarkets.size,
      matchedGamesCount,
      unmatchedMarkets,
      unmatchedGames,
      unmatchedMarketReasons,
      unmatchedGameReasons,
      unmatchedReasons,
      error:
        matchingStatus === "PARTIAL"
          ? `Matched ${matchedGamesCount} of ${games.length} game${games.length === 1 ? "" : "s"}; ${unmatchedMarkets.length} unmatched market${unmatchedMarkets.length === 1 ? "" : "s"}.`
          : undefined,
    },
  };
}

async function fetchBrowserPolymarket(games: AstroddsGameScan[] = []): Promise<BrowserPolymarketPayload> {
  const terms = mlbScheduleSearchTerms(games);
  const urls = terms.map((term) => polymarketEventsUrl(term));
  const marketUrls = terms.map((term) => polymarketMarketsUrl(term));
  const settled = await Promise.allSettled(
    urls.map(async (url) => {
      const response = await fetch(url.toString(), {
        cache: "no-store",
        headers: { accept: "application/json" },
      });

      if (!response.ok) throw new Error(`Polymarket Gamma API returned ${response.status} for ${url.toString()}`);
      const data = (await response.json()) as unknown;
      return Array.isArray(data) ? (data as GammaEvent[]) : [];
    }),
  );
  const marketSettled = await Promise.allSettled(
    marketUrls.map(async (url) => {
      const response = await fetch(url.toString(), {
        cache: "no-store",
        headers: { accept: "application/json" },
      });

      if (!response.ok) throw new Error(`Polymarket Gamma markets API returned ${response.status} for ${url.toString()}`);
      const data = (await response.json()) as unknown;
      return Array.isArray(data) ? (data as GammaMarket[]) : [];
    }),
  );
  const events = settled.flatMap((entry) => (entry.status === "fulfilled" ? entry.value : []));
  const directMarkets = marketSettled.flatMap((entry) => (entry.status === "fulfilled" ? entry.value : []));
  const errors = settled.flatMap((entry) => (entry.status === "rejected" ? [errorMessage(entry.reason)] : []));
  const marketErrors = marketSettled.flatMap((entry) => (entry.status === "rejected" ? [errorMessage(entry.reason)] : []));
  const normalized = normalizePolymarketSources(events, directMarkets, "MLB");
  const sourceUrl = [...urls, ...marketUrls].map(String).join(" | ");

  if (settled.every((entry) => entry.status === "rejected") && marketSettled.every((entry) => entry.status === "rejected")) {
    return {
      markets: [],
      diagnostics: {
        status: "FAILED",
        sourceMode: "FAILED",
        marketsFetched: 0,
        sportsMarketsDetected: 0,
        marketsMatchedToGames: 0,
        rawEventsFetched: 0,
        rawMarketsFetched: 0,
        rejectedNonMlbMarkets: 0,
        mlbMarketsDetected: 0,
        error: [...errors, ...marketErrors].join(" | ") || "Browser fallback could not reach Polymarket.",
        sourceUrl,
      },
      orderBookDiagnostics: {
        status: "NOT_CONNECTED",
        sourceMode: "FAILED",
        orderBooksRequested: 0,
        orderBooksFetched: 0,
        orderBooksFailed: 0,
        sourceUrl: "https://clob.polymarket.com/book",
        error: "Order books skipped because browser fallback could not reach Polymarket.",
      },
    };
  }

  const hydrated = await hydrateMarketsWithOrderBooks(normalized.markets, undefined, "BROWSER_FALLBACK");

  return {
    markets: hydrated.markets,
    diagnostics: {
      status: errors.length || marketErrors.length || normalized.acceptedRawMarkets.length === 0 ? "PARTIAL" : "CONNECTED_BROWSER",
      sourceMode: "BROWSER_FALLBACK",
      marketsFetched: normalized.rawMarketsFetched,
      sportsMarketsDetected: normalized.acceptedRawMarkets.length,
      marketsMatchedToGames: 0,
      rawEventsFetched: normalized.rawEventsFetched,
      rawMarketsFetched: normalized.rawMarketsFetched,
      rejectedNonMlbMarkets: normalized.rejectedMarkets.length,
      mlbMarketsDetected: normalized.acceptedRawMarkets.length,
      singleGameMlbMarketsDetected: normalized.markets.length,
      queryStrategiesUsed: ["sport keyword", "schedule team pair", "team + MLB/baseball context", "Gamma events endpoint", "Gamma markets endpoint"],
      teamSearchQueriesAttempted: terms.filter((term) => !polymarketSportQueryTerms("MLB").includes(term)).slice(0, 40),
      futuresRejected: normalized.rejectedMarkets.filter((market) => market.rejectedReason?.includes("futures") || market.rejectedReason?.includes("season/championship")).length,
      wrongSportsRejected: normalized.rejectedMarkets.filter((market) => market.rejectedReason?.includes("wrong sport")).length,
      noMlbTeamMatchRejected: normalized.rejectedMarkets.filter((market) => market.rejectedReason?.includes("no MLB team alias") || market.rejectedReason?.includes("no opponent match") || market.rejectedReason?.includes("no MLB game match") || market.rejectedReason?.includes("unrelated prediction")).length,
      unclearYesNoRejected: normalized.unclearYesNoRejected,
      rejectedMarkets: normalized.rejectedMarkets.slice(0, 20).map((market) => ({
        title: market.eventTitle && market.eventTitle !== market.title ? `${market.eventTitle} - ${market.title}` : market.title,
        rejectedReason: market.rejectedReason ?? "Rejected: no MLB game match",
      })),
      rawMarketSamples: normalized.rawMarketSamples,
      mlbCandidateMarketSamples: normalized.mlbCandidateMarketSamples,
      rejectionReasonCounts: normalized.rejectionReasonCounts,
      error:
        errors.length || marketErrors.length || normalized.acceptedRawMarkets.length === 0
          ? [[...errors, ...marketErrors].join(" | "), normalized.acceptedRawMarkets.length === 0 ? "Browser fallback connected to Polymarket, but no active single-game MLB markets were detected after team-alias filtering." : ""]
              .filter(Boolean)
              .join(" ")
          : undefined,
      sourceUrl,
    },
    orderBookDiagnostics: hydrated.diagnostics,
  };
}

async function fetchBrowserMlbWithWeather(): Promise<BrowserMlbPayload> {
  const url = mlbScheduleUrl();
  const response = await fetch(url.toString(), {
    cache: "no-store",
    headers: { accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`MLB StatsAPI returned ${response.status}`);
  }

  const data = (await response.json()) as MlbScheduleResponse;
  const games = data.dates?.flatMap((day) => day.games ?? []) ?? [];
  const rows = await Promise.all(
    games.map(async (game) => {
      const away = game.teams?.away?.team?.name ?? "Away";
      const home = game.teams?.home?.team?.name ?? "Home";
      const venue = game.venue?.name;
      const coords = venueCoordinates(game);
      const weather = await fetchWeatherContext(
        {
          latitude: coords?.latitude,
          longitude: coords?.longitude,
          startTime: game.gameDate,
          sport: "MLB",
        },
      );
      const awayPitcher = game.teams?.away?.probablePitcher?.fullName;
      const homePitcher = game.teams?.home?.probablePitcher?.fullName;
      const pitcherSummary =
        awayPitcher || homePitcher
          ? `${away}: ${awayPitcher ?? "TBD"} | ${home}: ${homePitcher ?? "TBD"}`
          : "Probable pitchers not posted yet.";
      const lineupsStatus = game.status?.abstractGameState === "Preview" ? "NOT_CONNECTED" : "PARTIAL";

      return {
        game: {
          id: `mlb-browser-${game.gamePk ?? compactId(`${away}-${home}-${game.gameDate ?? ""}`)}`,
          sport: "MLB",
          league: "MLB",
          game: `${away} vs ${home}`,
          awayTeam: away,
          homeTeam: home,
          startTime: game.gameDate,
          liveStatus: liveStatus(game),
          score: gameScore(game),
          period: game.linescore?.currentInningOrdinal
            ? `${game.linescore.currentInningOrdinal} ${game.linescore.inningState ?? ""}`.trim()
            : game.status?.detailedState ?? "Pregame",
          venue,
          weather,
          injuries: {
            status: "NOT_CONNECTED",
            source: "Source needed",
            summary: "NOT CONNECTED - MLB injury provider needed.",
          },
          lineups: {
            status: lineupsStatus,
            source: "MLB StatsAPI schedule (browser fallback)",
            summary:
              lineupsStatus === "PARTIAL"
                ? "PARTIAL - schedule feed only; confirmed starting lineups require a lineup source."
                : "NOT CONNECTED - confirmed lineups not available from this free schedule feed.",
          },
          keyContext: [
            `Probable pitchers: ${pitcherSummary}`,
            weather.summary,
            "Bullpen fatigue and handedness matchup prepared for paid/provider upgrade.",
          ],
          keyPlayerStatus: pitcherSummary,
          markets: [],
          dataStatus: dataStatusRank(["CONNECTED", weather.status, lineupsStatus]),
          source: "MLB StatsAPI public schedule + Open-Meteo weather (browser fallback)",
        } satisfies AstroddsGameScan,
        venueMapped: Boolean(coords),
      };
    }),
  );

  const probablePitchersFound = games.filter(hasProbablePitcher).length;
  const venuesFound = games.filter((game) => Boolean(game.venue?.name)).length;
  const gamesWithMappedCityOrStadium = rows.filter((row) => row.venueMapped).length;
  const weatherResultsFetched = rows.filter((row) => row.game.weather?.status === "CONNECTED").length;
  const missingPitchers = games.length - probablePitchersFound;
  const missingVenues = games.length - venuesFound;
  const unmappedVenues = games.length - gamesWithMappedCityOrStadium;
  const failedWeather = rows.filter((row) => row.game.weather?.status === "PARTIAL").length;
  const sportWarnings = [
    games.length === 0 ? "MLB StatsAPI connected through browser fallback, but no games returned for today plus the next few days." : "",
    missingPitchers > 0 ? `Probable pitchers missing for ${missingPitchers} game${missingPitchers === 1 ? "" : "s"}.` : "",
    missingVenues > 0 ? `Venues missing for ${missingVenues} game${missingVenues === 1 ? "" : "s"}.` : "",
  ].filter(Boolean);
  const weatherWarnings = [
    unmappedVenues > 0 ? `${unmappedVenues} venue${unmappedVenues === 1 ? "" : "s"} need location mapping.` : "",
    failedWeather > 0 ? `${failedWeather} weather request${failedWeather === 1 ? "" : "s"} returned partial data.` : "",
  ].filter(Boolean);

  return {
    games: rows.map((row) => row.game),
    sportApi: {
      sport: "MLB",
      status: sportWarnings.length ? "PARTIAL" : "CONNECTED_BROWSER",
      sourceMode: "BROWSER_FALLBACK",
      gamesFetched: games.length,
      probablePitchersFound,
      venuesFound,
      error: sportWarnings.length ? sportWarnings.join(" ") : undefined,
      sourceUrl: url.toString(),
    },
    weather: {
      status:
        games.length === 0
          ? "NOT_CONNECTED"
          : gamesWithMappedCityOrStadium === 0
            ? "NOT_CONNECTED"
            : weatherResultsFetched === gamesWithMappedCityOrStadium && unmappedVenues === 0
              ? "CONNECTED_BROWSER"
              : "PARTIAL",
      sourceMode: gamesWithMappedCityOrStadium > 0 || weatherResultsFetched > 0 ? "BROWSER_FALLBACK" : "FAILED",
      gamesWithMappedCityOrStadium,
      weatherResultsFetched,
      error: weatherWarnings.length ? weatherWarnings.join(" ") : undefined,
      sourceUrl: OPEN_METEO_FORECAST_URL,
    },
  };
}

function failedPolymarket(sourceUrl?: string, error?: string): AstroddsScanDiagnostics["polymarket"] {
  return {
    status: "FAILED",
    sourceMode: "FAILED",
    marketsFetched: 0,
    sportsMarketsDetected: 0,
    marketsMatchedToGames: 0,
    rawEventsFetched: 0,
    rawMarketsFetched: 0,
    rejectedNonMlbMarkets: 0,
    mlbMarketsDetected: 0,
    error,
    sourceUrl,
  };
}

function failedMlb(error?: string): BrowserMlbPayload {
  return {
    games: [],
    sportApi: {
      sport: "MLB",
      status: "FAILED",
      sourceMode: "FAILED",
      gamesFetched: 0,
      probablePitchersFound: 0,
      venuesFound: 0,
      error,
      sourceUrl: mlbScheduleUrl().toString(),
    },
    weather: {
      status: "NOT_CONNECTED",
      sourceMode: "FAILED",
      gamesWithMappedCityOrStadium: 0,
      weatherResultsFetched: 0,
      sourceUrl: OPEN_METEO_FORECAST_URL,
    },
  };
}

function sourceStatusFor(games: AstroddsGameScan[], polymarketDiagnostics: AstroddsScanDiagnostics["polymarket"]): AstroddsSourceStatusMap {
  const statuses = games.map((game) => game.dataStatus);

  return {
    polymarket: polymarketDiagnostics.status === "FAILED" ? "NOT_CONNECTED" : polymarketDiagnostics.sportsMarketsDetected > 0 ? "CONNECTED" : "PARTIAL",
    sportData: dataStatusRank(statuses),
    weather: dataStatusRank(games.map((game) => game.weather?.status ?? "NOT_CONNECTED")),
    lineups: dataStatusRank(games.map((game) => game.lineups?.status ?? "NOT_CONNECTED")),
    injuries: dataStatusRank(games.map((game) => game.injuries?.status ?? "NOT_CONNECTED")),
    keyPlayers: games.some((game) => !game.keyPlayerStatus.includes("NOT CONNECTED")) ? "PARTIAL" : "NOT_CONNECTED",
    wallets: "WALLET_LED",
  };
}

function warningList(games: AstroddsGameScan[], diagnostics: AstroddsScanDiagnostics) {
  const warnings: string[] = [BROWSER_WARNING];
  if (!games.length) warnings.push("No live MLB rows returned after browser fallback. Check Raw Source Debug for the failed source.");
  if (games.length && !diagnostics.matching.matchedMarketsCount) warnings.push("MLB schedule loaded, but no active single-game Polymarket markets matched. This is a market-matching issue or Polymarket may not currently list these games.");
  if (games.some((game) => game.dataStatus === "PARTIAL")) warnings.push("Some rows are partial because free sources do not include lineups, injuries, or player status.");
  if (games.some((game) => game.markets.length === 0)) warnings.push("Some MLB games have no matched Polymarket market yet.");
  return warnings;
}

export async function scanMlbWithBrowserFallback(serverResult?: AstroddsScanResult | null): Promise<AstroddsScanResult> {
  const generatedAt = new Date().toISOString();
  const sourceUrls = polymarketSportQueryTerms("MLB").map((term) => polymarketEventsUrl(term).toString()).join(" | ");
  const mlbSettled = await Promise.allSettled([fetchBrowserMlbWithWeather()]);
  const mlbPayload = mlbSettled[0].status === "fulfilled" ? mlbSettled[0].value : failedMlb(errorMessage(mlbSettled[0].reason));
  const polymarketSettled = await Promise.allSettled([fetchBrowserPolymarket(mlbPayload.games)]);
  const polymarketPayload =
    polymarketSettled[0].status === "fulfilled"
      ? polymarketSettled[0].value
      : {
          markets: [],
          diagnostics: failedPolymarket(sourceUrls, errorMessage(polymarketSettled[0].reason)),
          orderBookDiagnostics: {
            status: "FAILED" as const,
            sourceMode: "FAILED" as const,
            orderBooksRequested: 0,
            orderBooksFetched: 0,
            orderBooksFailed: 0,
            sourceUrl: "https://clob.polymarket.com/book",
            error: "Order books skipped because browser fallback Polymarket fetch failed.",
          },
        };
  const matched = attachMlbMarketsToGames(mlbPayload.games, polymarketPayload.markets);
  const decisionGames = applyDecisionEngine(matched.games);
  const bestPicks = rankedPicks(decisionGames, 10);
  const diagnostics: AstroddsScanDiagnostics = {
    polymarket: {
      ...polymarketPayload.diagnostics,
      marketsMatchedToGames: matched.matching.matchedMarketsCount,
      matchedMarketSamples: matched.games
        .flatMap((game) => game.markets.map((market) => `${game.game} | ${market.marketTitle} | ${market.pick}`))
        .slice(0, 10),
    },
    sportApi: mlbPayload.sportApi,
    weather: mlbPayload.weather,
    matching: matched.matching,
    orderBook: polymarketPayload.orderBookDiagnostics,
    lastErrors: [
      polymarketPayload.diagnostics.error,
      polymarketPayload.orderBookDiagnostics.error,
      mlbPayload.sportApi.error,
      mlbPayload.weather.error,
      matched.matching.error,
    ].filter(Boolean) as string[],
  };
  const serverErrors = serverResult?.diagnostics.lastErrors.length ? [`Server scan failed before fallback: ${serverResult.diagnostics.lastErrors.join(" | ")}`] : [];

  return {
    sport: "MLB",
    generatedAt,
    lastScanTime: generatedAt,
    sourceStatus: sourceStatusFor(decisionGames, diagnostics.polymarket),
    diagnostics,
    games: decisionGames,
    bestPicks,
    warnings: [...serverErrors, ...warningList(decisionGames, diagnostics), ...diagnostics.lastErrors].filter(Boolean),
  };
}

export function shouldUseBrowserFallback(result: AstroddsScanResult) {
  if (result.sport !== "MLB") return false;
  const statuses = [result.diagnostics.polymarket.status, result.diagnostics.sportApi.status, result.diagnostics.weather.status, result.diagnostics.orderBook.status];
  const errors = result.diagnostics.lastErrors.join(" ").toLowerCase();
  return statuses.includes("FAILED") || errors.includes("fetch failed");
}

export function isBrowserFallbackResult(result?: AstroddsScanResult | null) {
  if (!result) return false;
  return [
    result.diagnostics.polymarket.sourceMode,
    result.diagnostics.sportApi.sourceMode,
    result.diagnostics.weather.sourceMode,
    result.diagnostics.matching.sourceMode,
    result.diagnostics.orderBook.sourceMode,
  ].includes("BROWSER_FALLBACK");
}
