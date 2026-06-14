import { applyDecisionEngine, rankedPicks } from "./decision-engine";
import { buildMlbGameStatusValidation, buildMlbGameStatusValidationDiagnostics } from "../mlb/game-status-validation";
import { scanMLBGames, scanMLBGamesWithDiagnostics } from "./mlb";
import { scanMMAMarkets } from "./mma";
import { scanNBAGames } from "./nba";
import { scanNFLGames } from "./nfl";
import { scanNHLGames } from "./nhl";
import { fetchPolymarketSportsMarkets } from "./polymarket";
import { scanSoccerGames } from "./soccer";
import { scanTennisMatches } from "./tennis";
import { describeMlbMarketTeams, matchMlbMarketToGame } from "./mlb-teams";
import type {
  AstroddsGameScan,
  AstroddsMarketScan,
  AstroddsScanDiagnostics,
  AstroddsScanResult,
  AstroddsSourceStatusMap,
  AstroddsSport,
  AstroddsSportFilter,
} from "./types";
import { compactId, dataStatusRank, detectSport, tokenMatchScore } from "./normalize";

type ScanFn = (signal?: AbortSignal) => Promise<AstroddsGameScan[]>;

const scanFunctions: Partial<Record<AstroddsSport, ScanFn>> = {
  MLB: scanMLBGames,
  NFL: scanNFLGames,
  NBA: scanNBAGames,
  NHL: scanNHLGames,
  SOCCER: scanSoccerGames,
};

function marketKey(market: AstroddsMarketScan) {
  return `${market.marketId}-${market.pick}-${market.assetId ?? ""}`;
}

function marketOnlyGame(sport: AstroddsSport, market: AstroddsMarketScan): AstroddsGameScan {
  const reason =
    market.unmatchedReason ??
    (sport === "MLB"
      ? "Polymarket market found, but no matching MLB schedule game was found."
      : "Polymarket market found, but no matching sport schedule game was found.");

  return {
    id: `${sport.toLowerCase()}-market-${compactId(market.marketTitle)}-${compactId(market.pick)}`,
    sport,
    league: market.category ?? sport,
    game: market.marketTitle,
    players: market.outcomes,
    liveStatus: "UNKNOWN",
    score: "0-0",
    period: "Market only",
    weather: ["MLB", "NFL", "SOCCER", "TENNIS"].includes(sport)
      ? {
          status: "NOT_CONNECTED",
          source: "Source needed",
          impactScore: 0,
          impact: "NONE",
          summary: "NOT CONNECTED - sport schedule/venue required for weather.",
        }
      : undefined,
    injuries: {
      status: "NOT_CONNECTED",
      source: "Source needed",
      summary: "NOT CONNECTED - sport data source needed.",
    },
    lineups: {
      status: "NOT_CONNECTED",
      source: "Source needed",
      summary: "NOT CONNECTED - sport data source needed.",
    },
    keyContext: [reason],
    keyPlayerStatus: "MLB Data: NOT MATCHED",
    markets: [market],
    marketConnected: true,
    dataStatus: "PARTIAL",
    source: "Polymarket Gamma API market-only row",
    unmatchedReason: reason,
  };
}

function evaluateMarketMatch(game: AstroddsGameScan, market: AstroddsMarketScan, sport: AstroddsSport) {
  if (sport === "MLB") {
    return matchMlbMarketToGame({
      awayTeam: game.awayTeam,
      homeTeam: game.homeTeam,
      game: game.game,
      gameDate: game.startTime,
      marketTitle: market.marketTitle,
      marketPick: market.pick,
      marketOutcomes: market.outcomes,
      betType: market.betType,
      marketDate: market.marketDate ?? market.gameDate,
    });
  }

  const score = Math.max(
    tokenMatchScore(`${game.game} ${game.homeTeam ?? ""} ${game.awayTeam ?? ""}`, market.marketTitle),
    tokenMatchScore(`${game.players?.join(" ") ?? ""}`, market.marketTitle),
  );

  return {
    matched: score >= 0.28,
    score,
    reason: `Generic token score ${score.toFixed(2)} matched this market to the game.`,
    unmatchedReason: score > 0
      ? `Generic token score ${score.toFixed(2)} is below the 0.28 match threshold.`
      : "No shared game/team/player tokens found in the market title.",
  };
}

function unmatchedMarketReason(sport: AstroddsSport, market: AstroddsMarketScan, games: AstroddsGameScan[]) {
  if (!games.length) {
    return sport === "MLB"
      ? "Polymarket market found, but no matching MLB schedule game was found."
      : `${sport} schedule returned no game rows to match against.`;
  }

  if (sport === "MLB") {
    const detectedTeams = describeMlbMarketTeams(`${market.marketTitle} ${market.pick} ${market.outcomes.join(" ")}`);
    if (!detectedTeams.length) return "No MLB team alias found in market title, pick, or outcomes.";
    return `Detected ${detectedTeams.join(", ")}, but no fetched MLB schedule game matched those teams.`;
  }

  return "No fetched sport schedule game met the token match threshold for this market.";
}

function attachMarketsToGames(
  games: AstroddsGameScan[],
  markets: AstroddsMarketScan[],
  sport: AstroddsSport,
): { games: AstroddsGameScan[]; matching: AstroddsScanDiagnostics["matching"] } {
  const usedMarkets = new Set<string>();
  const unmatchedGames: string[] = [];
  const unmatchedGameReasons: Array<{ game: string; unmatchedReason: string }> = [];

  const withMarkets = games.map((game) => {
    const candidates = markets
      .map((market) => ({
        market,
        match: evaluateMarketMatch(game, market, sport),
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
        ? sport === "MLB"
          ? "MLB game found, but no matching Polymarket market was found."
          : `${sport} event found, but no matching Polymarket market was found.`
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
      marketConnected: matches.length > 0,
      unmatchedReason: matches.length ? undefined : bestUnmatchedReason,
    };
  });

  const unmatchedMarketRows = markets
    .filter((market) => !usedMarkets.has(marketKey(market)))
    .map((market) => {
      const unmatchedReason = unmatchedMarketReason(sport, market, games);
      return marketOnlyGame(sport, {
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
        ? "CONNECTED_SERVER"
        : "PARTIAL";

  return {
    games: [...withMarkets, ...unmatchedMarketRows],
    matching: {
      status: matchingStatus,
      sourceMode: matchingStatus === "NOT_CONNECTED" ? undefined : "SERVER",
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

function attachGameStatusValidationDiagnostics(diagnostics: AstroddsScanDiagnostics, games: AstroddsGameScan[]) {
  const validations = games
    .map((game) => game.gameStatusValidation)
    .filter((validation): validation is NonNullable<AstroddsGameScan["gameStatusValidation"]> => Boolean(validation));
  diagnostics.gameStatusValidationDiagnostics = buildMlbGameStatusValidationDiagnostics(validations);
}

function attachMlbGameStatusValidation(games: AstroddsGameScan[]) {
  return games.map((game) => {
    if (game.sport !== "MLB") return game;
    const marketDate = game.markets.find((market) => Boolean(market.marketDate))?.marketDate ?? game.startTime;
    return {
      ...game,
      gameStatusValidation: buildMlbGameStatusValidation({
        gameId: game.id,
        game: game.game,
        startTime: game.startTime,
        marketDate,
        liveStatus: game.liveStatus,
        mlbStatus: game.mlbStatus,
        marketTitle: game.markets[0]?.marketTitle ?? game.game,
        marketPick: game.markets[0]?.pick,
      }),
    };
  });
}

async function scanSportData(sport: AstroddsSport, markets: AstroddsMarketScan[], signal?: AbortSignal) {
  if (sport === "TENNIS") return scanTennisMatches(markets);
  if (sport === "MMA") return scanMMAMarkets(markets);

  const scanFn = scanFunctions[sport];
  if (!scanFn) return markets.map((market) => marketOnlyGame(sport, market));

  try {
    const games = await scanFn(signal);
    if (!games.length) return markets.map((market) => marketOnlyGame(sport, market));
    const matched = attachMarketsToGames(games, markets, sport).games;
    return sport === "MLB" ? attachMlbGameStatusValidation(matched) : matched;
  } catch (error) {
    return markets.length
      ? markets.map((market) => ({
          ...marketOnlyGame(sport, market),
          keyContext: [`Sport data fetch failed: ${error instanceof Error ? error.message : "unknown error"}`],
          dataStatus: "PARTIAL" as const,
        }))
      : [];
  }
}

function emptyDiagnostics(sport: AstroddsSportFilter): AstroddsScanDiagnostics {
  return {
    polymarket: {
      status: "NOT_CONNECTED",
      sourceMode: undefined,
      marketsFetched: 0,
      sportsMarketsDetected: 0,
      marketsMatchedToGames: 0,
      sourceUrl: "https://gamma-api.polymarket.com/events",
    },
    sportApi: {
      sport,
      status: "NOT_CONNECTED",
      sourceMode: undefined,
      gamesFetched: 0,
      probablePitchersFound: 0,
      venuesFound: 0,
      sourceUrl: sport === "MLB" ? "https://statsapi.mlb.com/api/v1/schedule" : undefined,
    },
    weather: {
      status: "NOT_CONNECTED",
      sourceMode: undefined,
      gamesWithMappedCityOrStadium: 0,
      weatherResultsFetched: 0,
      sourceUrl: "https://api.open-meteo.com/v1/forecast",
    },
    matching: {
      status: "NOT_CONNECTED",
      sourceMode: undefined,
      gamesCount: 0,
      polymarketMarketsCount: 0,
      matchedMarketsCount: 0,
      matchedGamesCount: 0,
      unmatchedMarkets: [],
      unmatchedGames: [],
      unmatchedMarketReasons: [],
      unmatchedGameReasons: [],
      unmatchedReasons: [],
    },
    orderBook: {
      status: "NOT_CONNECTED",
      sourceMode: undefined,
      orderBooksRequested: 0,
      orderBooksFetched: 0,
      orderBooksFailed: 0,
      sourceUrl: "https://clob.polymarket.com/book",
    },
    lastErrors: [],
    sourceDiagnostics: [],
  };
}

function sourceStatusFor(games: AstroddsGameScan[], polymarketStatus: "CONNECTED" | "PARTIAL"): AstroddsSourceStatusMap {
  const statuses = games.map((game) => game.dataStatus);

  return {
    polymarket: polymarketStatus,
    sportData: dataStatusRank(statuses),
    weather: dataStatusRank(games.map((game) => game.weather?.status ?? "NOT_CONNECTED")),
    lineups: dataStatusRank(games.map((game) => game.lineups?.status ?? "NOT_CONNECTED")),
    injuries: dataStatusRank(games.map((game) => game.injuries?.status ?? "NOT_CONNECTED")),
    keyPlayers: games.some((game) => !game.keyPlayerStatus.includes("NOT CONNECTED")) ? "PARTIAL" : "NOT_CONNECTED",
    wallets: "WALLET_LED",
  };
}

function warningList(games: AstroddsGameScan[], polymarketMarketCount: number) {
  const warnings: string[] = [];
  const mlbScheduleRows = games.filter((game) => game.sport === "MLB" && !game.source.toLowerCase().includes("market-only"));
  const mlbMatchedRows = mlbScheduleRows.filter((game) => game.markets.length > 0);

  if (!games.length) warnings.push("No live sport rows returned. Check Raw Source Debug for the failed source.");
  if (mlbScheduleRows.length && !mlbMatchedRows.length) {
    warnings.push("MLB schedule loaded, but no active single-game Polymarket markets matched. This is a market-matching issue or Polymarket may not currently list these games.");
  } else if (!polymarketMarketCount) {
    warnings.push("No active Polymarket sports markets matched this scan.");
  }
  if (games.some((game) => game.dataStatus === "DEMO_FALLBACK")) warnings.push("Demo fallback is active because a live source failed.");
  if (games.some((game) => game.dataStatus === "PARTIAL")) warnings.push("Some rows are partial because free sources do not include lineups, injuries, or player status.");
  if (games.some((game) => game.markets.length === 0)) warnings.push("Some games have no matched Polymarket market yet.");
  return warnings;
}

export async function scanAstroddsSport(sport: AstroddsSportFilter, signal?: AbortSignal): Promise<AstroddsScanResult> {
  const selectedSports: AstroddsSport[] =
    sport === "ALL" ? ["MLB", "NFL", "NBA", "NHL", "SOCCER", "TENNIS", "MMA"] : [sport];
  const generatedAt = new Date().toISOString();
  const diagnostics = emptyDiagnostics(sport);
  let polymarketWarning = "";
  let marketPayload: Awaited<ReturnType<typeof fetchPolymarketSportsMarkets>>;

  if (sport === "MLB") {
    let mlbGames: AstroddsGameScan[] = [];

    try {
      const mlbPayload = await scanMLBGamesWithDiagnostics(signal);
      mlbGames = mlbPayload.games;
      diagnostics.sportApi = mlbPayload.sportApi;
      diagnostics.weather = mlbPayload.weather;
      diagnostics.sourceDiagnostics = mlbPayload.sourceDiagnostics;
    } catch (error) {
      diagnostics.sportApi = {
        ...diagnostics.sportApi,
        sport: "MLB",
        status: "FAILED",
        sourceMode: "FAILED",
        error: `MLB API fetch failed: ${error instanceof Error ? error.message : "unknown error"}.`,
      };
      diagnostics.sourceDiagnostics = [
        {
          sourceLabel: "MLB StatsAPI",
          endpointLabel: "schedule",
          status: "FAILED",
          timedOut: false,
          sanitizedUrl: "https://statsapi.mlb.com/api/v1/schedule",
          errorMessage: error instanceof Error ? error.message : "unknown error",
          retryCount: 0,
        },
      ];
    }

    try {
      marketPayload = await fetchPolymarketSportsMarkets("MLB", signal, mlbGames);
      diagnostics.polymarket = marketPayload.diagnostics;
      diagnostics.orderBook = marketPayload.orderBookDiagnostics;
    } catch (error) {
      polymarketWarning = `Polymarket fetch failed: ${error instanceof Error ? error.message : "unknown error"}.`;
      marketPayload = {
        markets: [],
        rawMarkets: [],
        status: "PARTIAL",
        diagnostics: {
          ...diagnostics.polymarket,
          status: "FAILED",
          sourceMode: "FAILED",
          error: polymarketWarning,
        },
        orderBookDiagnostics: {
          ...diagnostics.orderBook,
          status: "FAILED",
          sourceMode: "FAILED",
          error: "Order books skipped because Polymarket market fetch failed.",
        },
      };
      diagnostics.polymarket = marketPayload.diagnostics;
      diagnostics.orderBook = marketPayload.orderBookDiagnostics;
    }

    const matched = attachMarketsToGames(mlbGames, marketPayload.markets, "MLB");
    const decisionGames = applyDecisionEngine(attachMlbGameStatusValidation(matched.games));
    const bestPicks = rankedPicks(decisionGames, 10);
    diagnostics.matching = matched.matching;
    attachGameStatusValidationDiagnostics(diagnostics, decisionGames);
    diagnostics.polymarket.marketsMatchedToGames = diagnostics.matching.matchedMarketsCount;
    diagnostics.polymarket.matchedMarketSamples = matched.games
      .flatMap((game) => game.markets.map((market) => `${game.game} | ${market.marketTitle} | ${market.pick}`))
      .slice(0, 10);
    diagnostics.lastErrors = [
      diagnostics.polymarket.error,
      diagnostics.sportApi.error,
      diagnostics.weather.error,
      diagnostics.matching.error,
      diagnostics.orderBook.error,
      polymarketWarning,
    ].filter(Boolean) as string[];

    return {
      sport,
      generatedAt,
      lastScanTime: generatedAt,
      sourceStatus: sourceStatusFor(decisionGames, marketPayload.status),
      diagnostics,
      games: decisionGames,
      bestPicks,
      warnings: [...diagnostics.lastErrors, ...warningList(decisionGames, marketPayload.markets.length)].filter(Boolean),
    };
  }

  try {
    marketPayload = await fetchPolymarketSportsMarkets(sport, signal);
    diagnostics.polymarket = marketPayload.diagnostics;
    diagnostics.orderBook = marketPayload.orderBookDiagnostics;
  } catch (error) {
    polymarketWarning = `Polymarket fetch failed: ${error instanceof Error ? error.message : "unknown error"}.`;
    marketPayload = {
      markets: [],
      rawMarkets: [],
      status: "PARTIAL",
      diagnostics: {
        ...diagnostics.polymarket,
        status: "FAILED",
        sourceMode: "FAILED",
        error: polymarketWarning,
      },
      orderBookDiagnostics: {
        ...diagnostics.orderBook,
        status: "FAILED",
        sourceMode: "FAILED",
        error: "Order books skipped because Polymarket market fetch failed.",
      },
    };
    diagnostics.polymarket = marketPayload.diagnostics;
    diagnostics.orderBook = marketPayload.orderBookDiagnostics;
  }

  const gamesBySport = await Promise.all(
    selectedSports.map(async (selectedSport) => {
      const sportMarkets = marketPayload.markets.filter((market) => {
        if (sport !== "ALL") return true;
        return detectSport(`${market.marketTitle} ${market.category ?? ""}`) === selectedSport;
      });

      if (selectedSport === "MLB") {
        try {
          const mlbPayload = await scanMLBGamesWithDiagnostics(signal);
          const matched = attachMarketsToGames(mlbPayload.games, sportMarkets, selectedSport);
          diagnostics.sportApi = mlbPayload.sportApi;
          diagnostics.weather = mlbPayload.weather;
          diagnostics.sourceDiagnostics = mlbPayload.sourceDiagnostics;
          diagnostics.matching = matched.matching;
          const games = attachMlbGameStatusValidation(matched.games);
          attachGameStatusValidationDiagnostics(diagnostics, games);
          return games;
        } catch (error) {
          const message = `MLB API fetch failed: ${error instanceof Error ? error.message : "unknown error"}.`;
          diagnostics.sportApi = {
            ...diagnostics.sportApi,
            sport: "MLB",
            status: "FAILED",
            sourceMode: "FAILED",
            error: message,
          };
          const matched = attachMarketsToGames([], sportMarkets, selectedSport);
          diagnostics.matching = matched.matching;
          const games = attachMlbGameStatusValidation(matched.games);
          attachGameStatusValidationDiagnostics(diagnostics, games);
          return games;
        }
      }

      return scanSportData(selectedSport, sportMarkets, signal);
    }),
  );

  const decisionGames = applyDecisionEngine(gamesBySport.flat());
  const bestPicks = rankedPicks(decisionGames, 10);
  diagnostics.polymarket.marketsMatchedToGames = diagnostics.matching.matchedMarketsCount;
  diagnostics.lastErrors = [
    diagnostics.polymarket.error,
    diagnostics.sportApi.error,
    diagnostics.weather.error,
    diagnostics.matching.error,
    diagnostics.orderBook.error,
    polymarketWarning,
  ].filter(Boolean) as string[];

  return {
    sport,
    generatedAt,
    lastScanTime: generatedAt,
    sourceStatus: sourceStatusFor(decisionGames, marketPayload.status),
    diagnostics,
    games: decisionGames,
    bestPicks,
    warnings: [...diagnostics.lastErrors, ...warningList(decisionGames, marketPayload.markets.length)].filter(Boolean),
  };
}
