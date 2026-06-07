import type { AstroddsGameScan, AstroddsMarketScan } from "./types";
import { compactId } from "./normalize";

function mmaFightFromMarket(market: AstroddsMarketScan): AstroddsGameScan {
  const title = market.marketTitle.replace(/\s+/g, " ").trim();

  return {
    id: `mma-market-${compactId(title)}`,
    sport: "MMA",
    league: "UFC / MMA",
    game: title,
    players: market.outcomes.filter((outcome) => !["Yes", "No"].includes(outcome)),
    liveStatus: "UNKNOWN",
    score: "0-0",
    period: "Fight market",
    injuries: {
      status: "NOT_CONNECTED",
      source: "Source needed",
      summary: "NOT CONNECTED - fighter injury/news source needed.",
    },
    lineups: {
      status: "NOT_CONNECTED",
      source: "Not applicable",
      summary: "Not applicable; weigh-in and short-notice replacement data needed.",
    },
    keyContext: [
      "Weight cut/weigh-in status: NOT CONNECTED - source needed.",
      "Short-notice replacement status: NOT CONNECTED - source needed.",
      "Style matchup model prepared but not connected.",
    ],
    keyPlayerStatus: "Fighter news, camp, and weigh-in status not connected.",
    markets: [market],
    dataStatus: "PARTIAL",
    source: "Polymarket market-led scan until MMA event/provider is connected",
  };
}

export function scanMMAMarkets(markets: AstroddsMarketScan[]): AstroddsGameScan[] {
  return markets.map(mmaFightFromMarket);
}
