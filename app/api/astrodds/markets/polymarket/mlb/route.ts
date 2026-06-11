import { NextResponse } from "next/server";

import { discoverPolymarketMlbMoneylineMarkets } from "@/lib/astrodss/sports-data/polymarket-mlb-markets";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const result = await discoverPolymarketMlbMoneylineMarkets();
    return NextResponse.json(result, {
      headers: {
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    return NextResponse.json(
      {
        status: "FAILED",
        marketPricesConnected: false,
        supportedMarkets: ["moneyline"],
        disabledMarkets: ["runline"],
        futureMarkets: ["total_runs"],
        markets: [],
        cacheUsed: false,
        cacheStatus: "missing",
        cacheAgeSeconds: undefined,
        cacheGeneratedAt: undefined,
        sourceDiagnostics: [
          {
            source: "Polymarket Gamma",
            endpointLabel: "MLB moneyline discovery",
            status: "FAILED",
            timeout: false,
            sanitizedUrl: "https://gamma-api.polymarket.com/events|markets",
            error: error instanceof Error ? error.message : "Unknown Polymarket MLB discovery failure",
            retryCount: 0,
          },
        ],
        warnings: ["Polymarket MLB moneyline discovery failed safely. Official picks remain blocked."],
        generatedAt: new Date().toISOString(),
      },
      {
        headers: {
          "Cache-Control": "no-store",
        },
      },
    );
  }
}
