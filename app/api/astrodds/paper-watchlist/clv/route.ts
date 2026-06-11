import { NextResponse } from "next/server";

import { updatePaperWatchlistMarketPrices } from "@/lib/astrodss/mlb/paper-watchlist-clv";
import { loadPaperWatchlistLedgerStatus } from "@/lib/astrodss/mlb/paper-watchlist-ledger";

export const dynamic = "force-dynamic";

export async function POST() {
  const result = await updatePaperWatchlistMarketPrices();
  const ledgerStatus = await loadPaperWatchlistLedgerStatus();

  return NextResponse.json({
    ok: result.ok,
    realMoneyTrading: "OFF",
    status: result.status,
    scannedCount: result.scannedCount,
    updatedCount: result.updatedCount,
    skippedCount: result.skippedCount,
    warnings: result.warnings,
    message: result.ok
      ? result.updatedCount > 0
        ? `Updated CLV snapshots for ${result.updatedCount} open rows.`
        : "No open rows changed CLV state."
      : "Paper watchlist CLV update could not run safely.",
    paperWatchlistClvDiagnostics: result,
    paperWatchlistLedgerDiagnostics: {
      ...ledgerStatus,
      rowsWithEntryPrice: result.summary.rowsWithEntryPrice,
      rowsWithLatestPrice: result.summary.rowsWithLatestPrice,
      rowsWithClosingPrice: result.summary.rowsWithClosingPrice,
      positiveClvRows: result.summary.positiveClvRows,
      negativeClvRows: result.summary.negativeClvRows,
      neutralClvRows: result.summary.neutralClvRows,
      missingClvRows: result.summary.missingClvRows,
      averageClv: result.summary.averageClv,
      averageClvPct: result.summary.averageClvPct,
      clvWarnings: result.summary.warnings,
    },
    recentRows: result.recentRows,
  });
}
