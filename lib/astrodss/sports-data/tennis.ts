import type { AstroddsGameScan, AstroddsMarketScan } from "./types";
import { compactId } from "./normalize";

function tennisGameFromMarket(market: AstroddsMarketScan): AstroddsGameScan {
  const title = market.marketTitle.replace(/\s+/g, " ").trim();

  return {
    id: `tennis-market-${compactId(title)}`,
    sport: "TENNIS",
    league: "Tennis",
    game: title,
    players: market.outcomes.filter((outcome) => !["Yes", "No"].includes(outcome)),
    liveStatus: "UNKNOWN",
    score: "0-0",
    period: "Market-led",
    weather: {
      status: "NOT_CONNECTED",
      source: "Source needed",
      impactScore: 0,
      impact: "NONE",
      summary: "NOT CONNECTED - outdoor tournament venue needed for weather.",
    },
    injuries: {
      status: "NOT_CONNECTED",
      source: "Source needed",
      summary: "NOT CONNECTED - injury/retirement risk source needed.",
    },
    lineups: {
      status: "NOT_CONNECTED",
      source: "Not applicable",
      summary: "Not applicable for tennis; player form and fatigue feeds needed.",
    },
    keyContext: [
      "Surface: NOT CONNECTED - tournament metadata needed.",
      "Fatigue/form: NOT CONNECTED - source needed.",
      "Retirement risk: NOT CONNECTED - source needed.",
    ],
    keyPlayerStatus: "Player form and injury risk not connected.",
    markets: [market],
    dataStatus: "PARTIAL",
    source: "Polymarket market-led scan until tennis schedule/provider is connected",
  };
}

export function scanTennisMatches(markets: AstroddsMarketScan[]): AstroddsGameScan[] {
  return markets.map(tennisGameFromMarket);
}
