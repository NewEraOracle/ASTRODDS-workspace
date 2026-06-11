import {
  discoverPolymarketMlbMoneylineMarkets,
  type PolymarketMlbMoneylineMarket,
  type PolymarketMlbSourceDiagnostic,
} from "../sports-data/polymarket-mlb-markets";
import { buildPolymarketMlbMatchDiagnostics } from "../sports-data/polymarket-mlb-match";
import { normalizeText } from "../sports-data/normalize";
import type { AstroddsGameScan, AstroddsMlbModelPick } from "../sports-data/types";
import {
  loadPaperWatchlistLedgerRows,
  writePaperWatchlistLedgerRows,
  type PaperWatchlistLedgerRow,
} from "./paper-watchlist-ledger";

export type PaperWatchlistClvStatus = "available" | "empty" | "missing";

export type PaperWatchlistClvSummary = {
  totalRows: number;
  openRows: number;
  settledRows: number;
  rowsWithEntryPrice: number;
  rowsWithLatestPrice: number;
  rowsWithClosingPrice: number;
  positiveClvRows: number;
  negativeClvRows: number;
  neutralClvRows: number;
  missingClvRows: number;
  averageClv: number | null;
  averageClvPct: number | null;
  warnings: string[];
};

export type PaperWatchlistClvDiagnostics = {
  status: PaperWatchlistClvStatus;
  summary: PaperWatchlistClvSummary;
  recentRows: PaperWatchlistLedgerRow[];
  warnings: string[];
  generatedAt: string;
  ledgerPath: string;
};

export type PaperWatchlistClvUpdateResult = PaperWatchlistClvDiagnostics & {
  ok: boolean;
  scannedCount: number;
  updatedCount: number;
  skippedCount: number;
  marketDiscovery: {
    status: "CONNECTED" | "PARTIAL" | "FAILED" | "NOT_CONNECTED";
    marketPricesConnected: boolean;
    cacheUsed: boolean;
    cacheStatus: string;
    cacheAgeSeconds?: number;
    cacheGeneratedAt?: string;
    moneylineMarketsFound: number;
    sourceDiagnostics: PolymarketMlbSourceDiagnostic[];
    warnings: string[];
    generatedAt: string;
  };
};

const LEDGER_PATH = ".astrodds/paper-watchlist-ledger.json";

function uniqueStrings(values: Array<string | undefined>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value && value.trim()))));
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function average(values: number[]) {
  if (!values.length) return null;
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function clvStatusForValue(value: number | null | undefined) {
  if (!isFiniteNumber(value)) return "missing" as const;
  if (value > 0) return "positive" as const;
  if (value < 0) return "negative" as const;
  return "neutral" as const;
}

function rowEntryProbability(row: PaperWatchlistLedgerRow) {
  return row.entryMarketProbability ?? row.marketProbability ?? null;
}

function summarizeRows(rows: PaperWatchlistLedgerRow[], warnings: string[]): PaperWatchlistClvSummary {
  const entryRows = rows.filter((row) => isFiniteNumber(rowEntryProbability(row)));
  const latestRows = rows.filter((row) => isFiniteNumber(row.latestMarketProbability));
  const closingRows = rows.filter((row) => isFiniteNumber(row.closingMarketProbability));
  const clvRows = rows.filter((row) => isFiniteNumber(row.clv));
  const clvPctRows = rows.filter((row) => isFiniteNumber(row.clvPct));
  const positiveClvRows = rows.filter((row) => row.clvStatus === "positive").length;
  const negativeClvRows = rows.filter((row) => row.clvStatus === "negative").length;
  const neutralClvRows = rows.filter((row) => row.clvStatus === "neutral").length;
  const missingClvRows = rows.filter((row) => row.clvStatus === "missing" || !row.clvStatus).length;

  return {
    totalRows: rows.length,
    openRows: rows.filter((row) => row.status === "open").length,
    settledRows: rows.filter((row) => row.status !== "open").length,
    rowsWithEntryPrice: entryRows.length,
    rowsWithLatestPrice: latestRows.length,
    rowsWithClosingPrice: closingRows.length,
    positiveClvRows,
    negativeClvRows,
    neutralClvRows,
    missingClvRows,
    averageClv: average(clvRows.map((row) => Number(row.clv))),
    averageClvPct: average(clvPctRows.map((row) => Number(row.clvPct))),
    warnings: uniqueStrings([
      ...warnings,
      rows.length < 5 ? "Small sample size - research only" : undefined,
      rows.some((row) => row.status === "open" && !isFiniteNumber(row.latestMarketProbability)) ? "Some open rows are missing latest market price snapshots." : undefined,
      rows.some((row) => !isFiniteNumber(row.entryMarketProbability) && !isFiniteNumber(row.marketProbability)) ? "Some rows are missing entry market probabilities." : undefined,
    ]),
  };
}

function sortRecentRows(rows: PaperWatchlistLedgerRow[], limit: number) {
  return [...rows]
    .sort((left, right) => new Date(right.updatedAt ?? right.createdAt).getTime() - new Date(left.updatedAt ?? left.createdAt).getTime())
    .slice(0, limit);
}

function paperModelPick(row: PaperWatchlistLedgerRow): AstroddsMlbModelPick {
  const selectedSide = row.selectedSide ?? row.researchSide;
  const team = selectedSide ?? row.homeTeam ?? row.awayTeam;
  return {
    modelLeanSide: row.homeTeam && row.awayTeam ? (selectedSide ? (normalizeText(team ?? "") === normalizeText(row.awayTeam) ? "AWAY" : "HOME") : "WAIT") : "WAIT",
    modelLeanTeam: team,
    modelConfidence: 0,
    modelScore: 0,
    dataQuality: "F",
    dataQualityScore: 0,
    pitcherScore: 0,
    lineupScore: 0,
    injuryScore: 0,
    teamFormScore: 0,
    weatherScore: 0,
    modelReason: "Paper watchlist CLV diagnostic only.",
    missingDataWarnings: ["Research only - no official pick data."],
    officialBetBlockedReason: "Paper watchlist CLV diagnostic only.",
    action: "WAIT_FOR_ODDS",
  };
}

function toDiagnosticGame(row: PaperWatchlistLedgerRow): AstroddsGameScan {
  return {
    id: row.ledgerId,
    sport: "MLB",
    league: "MLB",
    game: `${row.awayTeam ?? "Away"} vs ${row.homeTeam ?? "Home"}`,
    homeTeam: row.homeTeam,
    awayTeam: row.awayTeam,
    startTime: row.date,
    liveStatus: "PRE_GAME",
    keyContext: ["Research-only paper watchlist CLV diagnostic."],
    keyPlayerStatus: "Lineups, injuries, and weather not evaluated in CLV snapshot.",
    markets: [],
    dataStatus: "PARTIAL",
    source: "PAPER_WATCHLIST_LEDGER",
    modelPick: paperModelPick(row),
    unmatchedReason: "Research-only paper watchlist diagnostic game row.",
  };
}

function discoverySourceStatus(status: string, marketPricesConnected: boolean, cacheUsed: boolean) {
  if (cacheUsed) return "PARTIAL" as const;
  if (status === "FAILED") return "FAILED" as const;
  if (!marketPricesConnected) return "PARTIAL" as const;
  return "CONNECTED" as const;
}

function marketSourceLabel(cacheUsed: boolean, marketPricesConnected: boolean) {
  if (!marketPricesConnected) return "polymarket_unavailable";
  return cacheUsed ? "polymarket_cache" : "polymarket_live";
}

function applyClvSnapshot(
  row: PaperWatchlistLedgerRow,
  matchProbability: number | null,
  market?: PolymarketMlbMoneylineMarket,
  sourceLabel?: string,
  now = new Date().toISOString(),
): PaperWatchlistLedgerRow {
  const entryMarketProbability = row.entryMarketProbability ?? row.marketProbability ?? null;
  const latestMarketProbability = matchProbability ?? row.latestMarketProbability ?? null;
  const closingMarketProbability =
    market && (!market.active || market.closed)
      ? latestMarketProbability
      : row.closingMarketProbability ?? null;
  const clvBase = closingMarketProbability ?? latestMarketProbability;
  const clv = isFiniteNumber(entryMarketProbability) && isFiniteNumber(clvBase) ? clvBase - entryMarketProbability : null;
  const clvPct = isFiniteNumber(clv) ? clv * 100 : null;
  const clvStatus = clvStatusForValue(clv);
  const clvWarnings = uniqueStrings([
    ...(row.clvWarnings ?? []),
    !isFiniteNumber(entryMarketProbability) ? "Entry market probability unavailable." : undefined,
    !isFiniteNumber(latestMarketProbability) ? "Latest market probability unavailable." : undefined,
    market && market.active && !market.closed ? "Market is still open; closing probability is not yet confirmed." : undefined,
    !market ? "No matched Polymarket MLB market found for this ledger row." : undefined,
  ]);

  return {
    ...row,
    entryMarketProbability,
    latestMarketProbability,
    latestMarketCheckedAt: isFiniteNumber(latestMarketProbability) ? now : row.latestMarketCheckedAt,
    latestMarketSource: isFiniteNumber(latestMarketProbability) ? sourceLabel ?? row.latestMarketSource ?? "polymarket_live" : row.latestMarketSource,
    closingMarketProbability,
    closingMarketCheckedAt: isFiniteNumber(closingMarketProbability) ? now : row.closingMarketCheckedAt,
    clv,
    clvPct,
    clvStatus,
    clvWarnings,
  };
}

export async function loadPaperWatchlistClvDiagnostics(limit = 10): Promise<PaperWatchlistClvDiagnostics> {
  const { rows, available, warnings } = await loadPaperWatchlistLedgerRows();
  const summary = summarizeRows(rows, warnings);
  return {
    status: available ? (rows.length ? "available" : "empty") : "missing",
    summary,
    recentRows: sortRecentRows(rows, limit),
    warnings: summary.warnings,
    generatedAt: new Date().toISOString(),
    ledgerPath: LEDGER_PATH,
  };
}

export async function updatePaperWatchlistMarketPrices(limit = 10): Promise<PaperWatchlistClvUpdateResult> {
  const { rows, available, warnings } = await loadPaperWatchlistLedgerRows();
  if (!available) {
    const diagnostics = await loadPaperWatchlistClvDiagnostics(limit);
    return {
      ...diagnostics,
      ok: false,
      scannedCount: 0,
      updatedCount: 0,
      skippedCount: 0,
      marketDiscovery: {
        status: "FAILED",
        marketPricesConnected: false,
        cacheUsed: false,
        cacheStatus: "missing",
        cacheAgeSeconds: undefined,
        cacheGeneratedAt: undefined,
        moneylineMarketsFound: 0,
        sourceDiagnostics: [],
        warnings: ["Paper watchlist ledger unavailable."],
        generatedAt: new Date().toISOString(),
      },
    };
  }

  const openRows = rows.filter((row) => row.status === "open");
  if (!openRows.length) {
    const diagnostics = await loadPaperWatchlistClvDiagnostics(limit);
    return {
      ...diagnostics,
      ok: true,
      scannedCount: 0,
      updatedCount: 0,
      skippedCount: 0,
      marketDiscovery: {
        status: "NOT_CONNECTED",
        marketPricesConnected: false,
        cacheUsed: false,
        cacheStatus: "missing",
        cacheAgeSeconds: undefined,
        cacheGeneratedAt: undefined,
        moneylineMarketsFound: 0,
        sourceDiagnostics: [],
        warnings: ["No open paper watchlist rows to update."],
        generatedAt: new Date().toISOString(),
      },
      warnings: uniqueStrings([...diagnostics.warnings, "No open paper watchlist rows to update."]),
    };
  }

  const discovery = await discoverPolymarketMlbMoneylineMarkets();
  const sourceLabel = marketSourceLabel(Boolean(discovery.cacheUsed), discovery.marketPricesConnected);
  const sourceStatus = discoverySourceStatus(discovery.status, discovery.marketPricesConnected, Boolean(discovery.cacheUsed));
  const diagnosticsGames = openRows.map((row) => toDiagnosticGame(row));
  const marketProbabilitiesByGameId = Object.fromEntries(
    openRows
      .map((row) => [row.ledgerId, isFiniteNumber(row.calibratedProbability) ? row.calibratedProbability : isFiniteNumber(row.rawModelProbability) ? row.rawModelProbability : undefined] as const)
      .filter((entry): entry is [string, number] => typeof entry[1] === "number"),
  );
  const matchDiagnostics = buildPolymarketMlbMatchDiagnostics(diagnosticsGames, discovery.markets, {
    calibrationQuality: "research_only",
    modelProbabilitiesByGameId: marketProbabilitiesByGameId,
  });
  const matchesByGameId = new Map(matchDiagnostics.matches.map((match) => [match.gameId, match]));
  const marketsById = new Map(discovery.markets.map((market) => [market.marketId, market]));

  let updatedCount = 0;
  let skippedCount = 0;
  const now = new Date().toISOString();
  const nextRows = rows.map((row) => {
    if (row.status !== "open") return row;
    const match = matchesByGameId.get(row.ledgerId);
    const matchedMarket = match?.matchedMarketId ? marketsById.get(match.matchedMarketId) : undefined;
    const nextRow = applyClvSnapshot(row, match?.marketProbability ?? null, matchedMarket, sourceLabel, now);

    const changed =
      nextRow.entryMarketProbability !== row.entryMarketProbability ||
      nextRow.latestMarketProbability !== row.latestMarketProbability ||
      nextRow.latestMarketCheckedAt !== row.latestMarketCheckedAt ||
      nextRow.latestMarketSource !== row.latestMarketSource ||
      nextRow.closingMarketProbability !== row.closingMarketProbability ||
      nextRow.closingMarketCheckedAt !== row.closingMarketCheckedAt ||
      nextRow.clv !== row.clv ||
      nextRow.clvPct !== row.clvPct ||
      nextRow.clvStatus !== row.clvStatus;

    if (changed) updatedCount += 1;
    else skippedCount += 1;

    return nextRow;
  });

  if (updatedCount) {
    await writePaperWatchlistLedgerRows(nextRows);
  }

  const summary = summarizeRows(nextRows, uniqueStrings([
    ...warnings,
    ...discovery.warnings,
    ...matchDiagnostics.warnings,
    updatedCount ? undefined : "No open rows changed CLV state.",
    discovery.marketPricesConnected ? undefined : "Polymarket market prices are not connected; CLV updates are diagnostic-only.",
  ]));

  return {
    ok: true,
    status: nextRows.length ? "available" : "empty",
    summary,
    recentRows: sortRecentRows(nextRows, limit),
    warnings: summary.warnings,
    generatedAt: new Date().toISOString(),
    ledgerPath: LEDGER_PATH,
    scannedCount: openRows.length,
    updatedCount,
    skippedCount,
    marketDiscovery: {
      status: sourceStatus,
      marketPricesConnected: discovery.marketPricesConnected,
      cacheUsed: Boolean(discovery.cacheUsed),
      cacheStatus: discovery.cacheStatus,
      cacheAgeSeconds: discovery.cacheAgeSeconds,
      cacheGeneratedAt: discovery.cacheGeneratedAt,
      moneylineMarketsFound: discovery.markets.length,
      sourceDiagnostics: discovery.sourceDiagnostics,
      warnings: discovery.warnings,
      generatedAt: discovery.generatedAt,
    },
  };
}
