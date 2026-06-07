import { NextResponse } from "next/server";

import {
  fetchMLBFinalResults,
  findResultForPaperTrade,
  resolveMLBPaperTrade,
  summarizePaperPerformance,
  type AstroddsPaperTrade,
  type MlbFinalResult,
  type MlbResultDateRange,
} from "@/lib/astrodss/sports-data/mlb-results";
import { addDaysIsoDate, todayIsoDate } from "@/lib/astrodss/sports-data/normalize";

type ResolveRequest = {
  trades?: AstroddsPaperTrade[];
  dateRange?: MlbResultDateRange;
};

function dateRangeFromTrades(trades: AstroddsPaperTrade[], requested?: MlbResultDateRange): MlbResultDateRange {
  if (requested?.startDate || requested?.endDate) return requested;

  const timestamps = trades
    .map((trade) => new Date(trade.createdAt).getTime())
    .filter((time) => Number.isFinite(time));

  if (!timestamps.length) {
    return {
      startDate: addDaysIsoDate(-7),
      endDate: todayIsoDate(),
    };
  }

  const first = new Date(Math.min(...timestamps));
  first.setDate(first.getDate() - 1);
  const last = new Date(Math.max(...timestamps));
  last.setDate(last.getDate() + 7);

  return {
    startDate: first.toISOString().slice(0, 10),
    endDate: last.toISOString().slice(0, 10),
  };
}

function summaryFor(trades: AstroddsPaperTrade[], errors: string[] = []) {
  const performance = summarizePaperPerformance(trades);

  return {
    resolved: trades.filter((trade) => ["WIN", "LOSS", "VOID", "UNKNOWN"].includes(trade.status)).length,
    pending: performance.pending,
    wins: performance.wins,
    losses: performance.losses,
    voids: performance.voids,
    unknown: performance.unknown,
    errors,
  };
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as ResolveRequest;
  const trades: AstroddsPaperTrade[] = Array.isArray(body.trades) ? body.trades : [];
  const mlbTrades = trades.filter((trade) => trade.sport === "MLB");
  const errors: string[] = [];

  if (!trades.length) {
    return NextResponse.json({
      ...summaryFor([], []),
      trades: [],
      performance: summarizePaperPerformance([]),
    });
  }

  let results: MlbFinalResult[] = [];
  try {
    results = await fetchMLBFinalResults(dateRangeFromTrades(mlbTrades, body.dateRange));
  } catch (error) {
    errors.push(error instanceof Error ? error.message : "Unknown MLB results fetch failure.");
  }

  const resolvedTrades: AstroddsPaperTrade[] = trades.map((trade) => {
    if (trade.status !== "PENDING" || trade.sport !== "MLB") return trade;
    const result = findResultForPaperTrade(trade, results);
    return resolveMLBPaperTrade(trade, result);
  });

  return NextResponse.json({
    ...summaryFor(resolvedTrades, errors),
    trades: resolvedTrades,
    performance: summarizePaperPerformance(resolvedTrades),
    resultsFetched: results.length,
  });
}
