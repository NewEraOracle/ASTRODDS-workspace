import { NextResponse } from "next/server";

import { loadPaperWatchlistClvDiagnostics } from "@/lib/astrodss/mlb/paper-watchlist-clv";
import { loadPaperWatchlistLedgerStatus } from "@/lib/astrodss/mlb/paper-watchlist-ledger";

export const dynamic = "force-dynamic";

export async function GET() {
  const [status, clv] = await Promise.all([
    loadPaperWatchlistLedgerStatus(),
    loadPaperWatchlistClvDiagnostics(),
  ]);

  return NextResponse.json({
    ok: true,
    realMoneyTrading: "OFF",
    paperWatchlistLedgerDiagnostics: {
      ...status,
      rowsWithEntryPrice: clv.summary.rowsWithEntryPrice,
      rowsWithLatestPrice: clv.summary.rowsWithLatestPrice,
      rowsWithClosingPrice: clv.summary.rowsWithClosingPrice,
      positiveClvRows: clv.summary.positiveClvRows,
      negativeClvRows: clv.summary.negativeClvRows,
      neutralClvRows: clv.summary.neutralClvRows,
      missingClvRows: clv.summary.missingClvRows,
      averageClv: clv.summary.averageClv,
      averageClvPct: clv.summary.averageClvPct,
      clvWarnings: clv.summary.warnings,
    },
    paperWatchlistClvDiagnostics: clv,
    recentRows: status.recentRows,
    warnings: [...status.warnings, ...clv.warnings],
    ledgerPath: status.ledgerPath,
  });
}
