import { NextResponse } from "next/server";

import { loadStrongBuyLedgerStatus } from "@/lib/astrodss/mlb/strong-buy-ledger";

export const dynamic = "force-dynamic";

export async function GET() {
  const summary = await loadStrongBuyLedgerStatus();

  return NextResponse.json({
    ok: true,
    realMoneyTrading: "OFF",
    manualOnly: true,
    paperOnly: true,
    totalTracked: summary.totalTracked,
    open: summary.open,
    settled: summary.settled,
    wins: summary.wins,
    losses: summary.losses,
    winRate: summary.winRate,
    paperPnL: summary.paperPnL,
    currentBankroll: summary.currentBankroll,
    averageCLV: summary.averageCLV,
    averageStake: summary.averageStake,
    recentBets: summary.recentBets,
    exposure: {
      openStrongBuyCount: summary.openStrongBuyCount,
      totalOpenStakeAmount: summary.totalOpenStakeAmount,
      totalOpenExposurePercent: summary.totalOpenExposurePercent,
      remainingUnexposedBankroll: summary.remainingUnexposedBankroll,
      exposureLabel: summary.exposureLabel,
    },
    warnings: summary.warnings,
    ledgerPath: summary.ledgerPath,
    generatedAt: summary.generatedAt,
  }, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
