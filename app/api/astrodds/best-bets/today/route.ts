import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

type BestBetRowResponse = {
  status: "strong_buy" | "buy" | "watch" | "blocked";
};

type UnifiedBestBetsPayload = {
  bestBetsDiagnostics?: Record<string, unknown>;
  bestBetRows?: BestBetRowResponse[];
  strongBuyLedgerDiagnostics?: Record<string, unknown>;
  errors?: string[];
};

function statusRank(status: BestBetRowResponse["status"]) {
  if (status === "strong_buy") return 4;
  if (status === "buy") return 3;
  if (status === "watch") return 2;
  return 1;
}

export async function GET(request: Request) {
  const unifiedUrl = new URL("/api/astrodds/signals/unified?sport=MLB", request.url);
  const response = await fetch(unifiedUrl, {
    cache: "no-store",
    headers: {
      "x-astrodds-best-bets": "today",
    },
  });

  if (!response.ok) {
    return NextResponse.json({
      ok: false,
      realMoneyTrading: "OFF",
      manualOnly: true,
      paperOnly: true,
      bestBetsDiagnostics: {
        available: false,
        totalRowsEvaluated: 0,
        strongBuyCount: 0,
        buyCount: 0,
        watchCount: 0,
        blockedCount: 0,
        warnings: [`Unified MLB route failed with ${response.status}.`],
      },
      bestBetRows: [],
    }, { status: 200, headers: { "Cache-Control": "no-store" } });
  }

  const payload = (await response.json()) as UnifiedBestBetsPayload;
  const rows = [...(payload.bestBetRows ?? [])].sort((left, right) => statusRank(right.status) - statusRank(left.status));

  return NextResponse.json({
    ok: true,
    realMoneyTrading: "OFF",
    manualOnly: true,
    paperOnly: true,
    bestBetsDiagnostics: payload.bestBetsDiagnostics ?? {
      available: false,
      totalRowsEvaluated: 0,
      strongBuyCount: 0,
      buyCount: 0,
      watchCount: 0,
      blockedCount: 0,
      warnings: ["Best Bets diagnostics missing from unified route."],
    },
    bestBetRows: rows,
    strongBuyLedgerDiagnostics: payload.strongBuyLedgerDiagnostics ?? null,
    warnings: payload.errors ?? [],
  }, {
    headers: {
      "Cache-Control": "no-store",
    },
  });
}
