import type { AstroddsGameScan, AstroddsMarketScan, AstroddsSport } from "./types";

export const ASTRODDS_SCORE_WEIGHTS = {
  sportsData: 40,
  marketPrice: 25,
  liveGameState: 15,
  walletIntelligence: 15,
  riskManagement: 5,
};

function clamp(value: number, max = 100) {
  return Math.max(0, Math.min(max, Math.round(value)));
}

function dataCompleteness(game: AstroddsGameScan) {
  let score = 8;
  if (game.dataStatus === "CONNECTED") score += 14;
  if (game.dataStatus === "PARTIAL") score += 6;
  if (game.dataStatus === "WALLET_LED") score -= 4;
  if (game.dataStatus === "DEMO_FALLBACK") score -= 10;
  if (game.weather?.status === "CONNECTED") score += 5;
  if (game.lineups?.status === "CONNECTED") score += 5;
  if (game.lineups?.status === "PARTIAL") score += 3;
  if (game.injuries?.status === "CONNECTED") score += 4;
  if (game.injuries?.status === "PARTIAL") score += 2;
  if (game.keyPlayerStatus && !game.keyPlayerStatus.includes("NOT CONNECTED")) score += 5;
  return clamp(score, 40);
}

function sportSpecificScore(game: AstroddsGameScan, market: AstroddsMarketScan) {
  let score = dataCompleteness(game);
  const keyText = `${game.keyContext.join(" ")} ${market.marketTitle}`.toLowerCase();

  if (game.sport === "MLB") {
    if (keyText.includes("probable pitchers") && !keyText.includes("not posted")) score += 5;
    if (market.betType === "TOTAL" && (game.weather?.impactScore ?? 0) >= 25) score += 5;
    if (game.venue) score += 2;
  }

  if (game.sport === "NFL") {
    if (!game.keyPlayerStatus.includes("NOT CONNECTED")) score += 8;
    if (market.betType === "TOTAL" && (game.weather?.impactScore ?? 0) >= 25) score += 5;
  }

  if (game.sport === "NBA" && !game.keyPlayerStatus.includes("NOT CONNECTED")) score += 8;
  if (game.sport === "NHL" && !game.keyPlayerStatus.includes("NOT CONNECTED")) score += 8;
  if (game.sport === "SOCCER" && keyText.includes("draw")) score += 2;
  if (game.sport === "TENNIS" && keyText.includes("surface") && !keyText.includes("not connected")) score += 6;
  if (game.sport === "MMA" && !game.keyPlayerStatus.includes("not connected")) score += 6;

  return clamp(score, 40);
}

function priceScore(price: number) {
  if (price <= 0.02 || price >= 0.98) return 3;
  if (price >= 0.42 && price <= 0.62) return 23;
  if (price >= 0.32 && price <= 0.72) return 19;
  if (price >= 0.22 && price <= 0.8) return 14;
  return 8;
}

function marketQualityScore(market: AstroddsMarketScan) {
  let score = priceScore(market.currentPrice);
  if ((market.volume ?? 0) > 50000) score += 2;
  if ((market.liquidity ?? 0) > 10000) score += 2;
  if ((market.spread ?? 0.04) <= 0.03) score += 1;
  if (market.orderBook) {
    score = Math.max(score, market.orderBook.orderBookScore);
    if (market.orderBook.status === "EXCELLENT") score += 2;
    if (market.orderBook.status === "GOOD") score += 1;
    if (market.orderBook.status === "POOR") score -= 6;
    if (market.orderBook.status === "NO_LIQUIDITY") score -= 12;
    if (market.orderBook.fillStatus !== "OK") score -= 6;
  } else {
    score -= 4;
  }
  if (market.status !== "ACTIVE") score -= 8;
  return clamp(score, 25);
}

function liveStateScore(game: AstroddsGameScan, market: AstroddsMarketScan) {
  let score = 7;
  if (game.liveStatus === "PRE_GAME") score += 2;
  if (game.liveStatus === "LIVE") score += 4;
  if (game.liveStatus === "FINAL") score = 0;
  if (market.entryPrice && market.currentPrice - market.entryPrice > 0.2) score += 3;
  return clamp(score, 15);
}

function walletScore(market: AstroddsMarketScan) {
  const support = market.walletSupport;
  if (!support || support.rank === "NONE") return 2;
  if (support.rank === "DIAMOND_ELITE_WALLET") return 15;
  if (support.rank === "GOLD_WALLET") return 12;
  if (support.rank === "PROMISING_WATCH") return 8;
  return 4;
}

function riskScore(game: AstroddsGameScan, market: AstroddsMarketScan) {
  let score = 4;
  if (market.status !== "ACTIVE") score -= 2;
  if (game.dataStatus === "DEMO_FALLBACK") score -= 3;
  if (game.dataStatus === "WALLET_LED") score -= 1;
  if (market.currentPrice >= 0.78 || market.currentPrice <= 0.18) score -= 1;
  return clamp(score, 5);
}

export function entryQuality(price: number, marketScore: number) {
  if (price >= 0.82 || marketScore < 8) return "NO_ENTRY" as const;
  if (marketScore >= 22 && price >= 0.42 && price <= 0.62) return "EXCELLENT" as const;
  if (marketScore >= 18 && price <= 0.7) return "GOOD" as const;
  if (marketScore >= 12 && price <= 0.77) return "FAIR" as const;
  return "STRETCHED" as const;
}

export function missingWarnings(game: AstroddsGameScan, market?: AstroddsMarketScan) {
  const warnings: string[] = [];
  if (game.dataStatus === "DEMO_FALLBACK") warnings.push("Demo fallback active - live source failed.");
  if (game.dataStatus === "WALLET_LED") warnings.push("Sport data not connected; market-led only.");
  if (game.dataStatus === "PARTIAL") warnings.push("Sports data is partial.");
  if (game.lineups?.status === "NOT_CONNECTED") warnings.push("Lineups not connected.");
  if (game.injuries?.status === "NOT_CONNECTED") warnings.push("Injuries not connected.");
  if (game.weather?.status === "NOT_CONNECTED" && ["MLB", "NFL", "SOCCER", "TENNIS"].includes(game.sport)) warnings.push("Weather not connected.");
  if (game.keyPlayerStatus.includes("NOT CONNECTED")) warnings.push("Key player/pitcher/goalie context missing.");
  if (game.sport === "MLB") {
    warnings.push("News: NOT CONNECTED - source needed.");
    warnings.push("Team Form: NOT CONNECTED - source needed.");
  }
  if (!market?.orderBook) warnings.push("Order book not connected.");
  if (market?.orderBook?.status === "POOR") warnings.push("Order book is poor; spread/liquidity blocks Strong Buy.");
  if (market?.orderBook?.status === "NO_LIQUIDITY") warnings.push("No order book liquidity for a $50 paper fill.");
  if (market?.orderBook?.fillStatus && market.orderBook.fillStatus !== "OK") warnings.push("$50 paper fill cannot fully complete at current asks.");
  return warnings;
}

export function scoreMarket(game: AstroddsGameScan, market: AstroddsMarketScan) {
  const sportsData = sportSpecificScore(game, market);
  const marketPrice = marketQualityScore(market);
  const liveGameState = liveStateScore(game, market);
  const walletIntelligence = walletScore(market);
  const riskManagement = riskScore(game, market);
  const total = sportsData + marketPrice + liveGameState + walletIntelligence + riskManagement;

  return {
    sportsData,
    marketPrice,
    liveGameState,
    walletIntelligence,
    riskManagement,
    total: clamp(total),
    entryQuality: market.orderBook?.entryQuality ?? entryQuality(market.currentPrice, marketPrice),
    missingDataWarnings: missingWarnings(game, market),
  };
}

export function sportRiskNote(sport: AstroddsSport) {
  switch (sport) {
    case "MLB":
      return "Pitchers, lineups, weather, ballpark, bullpen fatigue, and price discipline drive the model.";
    case "NFL":
      return "QB status, injuries, wind/weather, matchup quality, rest, and price discipline drive the model.";
    case "NBA":
      return "Star injuries, lineups, rest, back-to-back spots, pace, and price movement drive the model.";
    case "NHL":
      return "Starting goalie, rest, special teams, shot profile, live score, and price movement drive the model.";
    case "SOCCER":
      return "Starting XI, draw risk, motivation, congestion, weather, red cards, and price drive the model.";
    case "TENNIS":
      return "Surface, fatigue, form, injury/retirement risk, tournament stage, and price drive the model.";
    case "MMA":
      return "Style matchup, injury rumors, weigh-ins, short-notice changes, camp news, and price drive the model.";
    default:
      return "Sport-specific context and market price drive the model.";
  }
}
