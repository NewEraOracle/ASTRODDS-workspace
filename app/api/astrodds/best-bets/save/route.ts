import { NextResponse } from "next/server";

import { saveStrongBuyLedgerRow } from "@/lib/astrodss/mlb/strong-buy-ledger";
import type { BestBetRow } from "@/lib/astrodss/mlb/strong-buy-gate";

export const dynamic = "force-dynamic";

type SaveBestBetRequest = {
  row?: BestBetRow;
};

function canSaveBestBet(row: BestBetRow) {
  return row.marketType === "moneyline" && row.manualOnly && row.paperOnly && row.realMoneyDisabled;
}

export async function POST(request: Request) {
  const body = (await request.json().catch(() => ({}))) as SaveBestBetRequest;
  const row = body.row;

  if (!row || !canSaveBestBet(row)) {
    return NextResponse.json({
      ok: false,
      realMoneyTrading: "OFF",
      manualOnly: true,
      paperOnly: true,
      message: "No eligible Best Bet row was supplied.",
    }, { status: 400, headers: { "Cache-Control": "no-store" } });
  }

  const result = await saveStrongBuyLedgerRow(row, { manuallyTaken: true });

  return NextResponse.json({
    ok: true,
    realMoneyTrading: "OFF",
    manualOnly: true,
    paperOnly: true,
    message: `Saved ${row.awayTeam ?? "Away"} @ ${row.homeTeam ?? "Home"} as a manually tracked bet.`,
    saved: result.saved,
    strongBuyLedgerDiagnostics: result.summary,
    warnings: result.warnings,
  }, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
