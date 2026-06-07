import type {
  AstroddsConfidence,
  AstroddsEdgeAssessment,
  AstroddsGameScan,
  AstroddsMarketScan,
  AstroddsProbabilityAssessment,
  AstroddsWalletRank,
} from "./types";
import { estimateMlbBetProbability } from "./probability-engine";

function clamp(value: number, max: number) {
  return Math.max(0, Math.min(max, Math.round(value)));
}

function pitcherConnected(game: AstroddsGameScan) {
  const text = game.keyPlayerStatus.toLowerCase();
  return Boolean(game.keyPlayerStatus && !text.includes("not posted") && !text.includes("not connected") && !text.includes("tbd"));
}

function preferredPriceScore(price: number) {
  if (!Number.isFinite(price) || price <= 0 || price >= 1) return 0;
  if (price >= 0.4 && price <= 0.65) return 22;
  if (price >= 0.35 && price < 0.4) return 15;
  if (price > 0.65 && price <= 0.8) return 14;
  if (price < 0.35) return 9;
  return 5;
}

function walletScore(rank?: AstroddsWalletRank) {
  if (rank === "DIAMOND_ELITE_WALLET") return 15;
  if (rank === "GOLD_WALLET") return 12;
  if (rank === "PROMISING_WATCH") return 7;
  if (rank === "DATA_ONLY") return 3;
  return 0;
}

function exactPick(market: AstroddsMarketScan) {
  if (market.probability?.decision && market.edge?.exactPick) return market.edge.exactPick;
  const price = market.currentPrice.toFixed(2);
  if (market.betType === "MONEYLINE") return `Bet ${market.pick} Moneyline at ${price}`;
  if (market.betType === "SPREAD") return `Bet ${market.pick} Run Line at ${price}`;
  if (market.betType === "TOTAL") return `Bet ${market.pick} at ${price}`;
  return `Bet ${market.pick} at ${price}`;
}

function sportsMatchupScore(game: AstroddsGameScan, market: AstroddsMarketScan, missingData: string[], dataWarnings: string[]) {
  let score = 8;

  if (game.dataStatus === "CONNECTED") score += 8;
  if (game.dataStatus === "PARTIAL") score += 4;
  if (game.venue) score += 3;

  if (pitcherConnected(game)) {
    score += market.betType === "MONEYLINE" || market.betType === "TOTAL" ? 8 : 5;
  } else {
    missingData.push("Pitcher matchup is not fully connected.");
    if (market.betType === "MONEYLINE" || market.betType === "TOTAL") dataWarnings.push("Pitcher data is partial, so confidence is reduced.");
  }

  if (game.weather?.status === "CONNECTED") {
    score += market.betType === "TOTAL" ? 7 : 3;
  } else if (market.betType === "TOTAL") {
    missingData.push("Weather is missing for this MLB total.");
    dataWarnings.push("Missing weather prevents a Strong Buy on totals.");
  }

  if (game.lineups?.status === "CONNECTED") score += 3;
  else missingData.push("Lineup source is not connected.");

  if (game.injuries?.status === "CONNECTED" || game.injuries?.status === "PARTIAL") score += 2;
  else missingData.push("News/injury source is not connected.");

  missingData.push("Team Form: NOT CONNECTED - source needed.");
  missingData.push("Recent team news: NOT CONNECTED - source needed.");

  return clamp(score, 35);
}

function marketValueScore(market: AstroddsMarketScan, probability: AstroddsProbabilityAssessment, riskWarnings: string[]) {
  let score = 0;

  if (market.currentPrice < 0.35) riskWarnings.push("Entry price is low but high risk; needs stronger data support.");
  if (market.currentPrice > 0.8) riskWarnings.push("Entry price is high and usually low value.");
  if (market.status !== "ACTIVE") {
    score -= 8;
    riskWarnings.push("Market is not active.");
  }
  if (!Number.isFinite(market.currentPrice)) {
    riskWarnings.push("Missing Polymarket entry price.");
    return 0;
  }

  if (probability.edge >= 0.12) score = 25;
  else if (probability.edge >= 0.08) score = 21;
  else if (probability.edge >= 0.05) score = 17;
  else if (probability.edge >= 0.02) score = 12;
  else if (probability.edge >= 0) score = 8;
  else score = 3;

  score = Math.max(score, Math.min(12, preferredPriceScore(market.currentPrice)));

  return clamp(score, 25);
}

function orderBookScore(market: AstroddsMarketScan, riskWarnings: string[]) {
  if (!market.orderBook) {
    riskWarnings.push("Order book missing; Elite disabled.");
    return 0;
  }

  if (market.orderBook.status === "EXCELLENT") return 15;
  if (market.orderBook.status === "GOOD") return 12;
  if (market.orderBook.status === "FAIR") return 8;
  if (market.orderBook.status === "POOR") {
    riskWarnings.push("Order book is poor; spread/liquidity caps this at WATCH.");
    return 3;
  }
  if (market.orderBook.status === "NO_LIQUIDITY") {
    riskWarnings.push("No order book liquidity for the $50 paper fill.");
    return 0;
  }

  return 0;
}

function riskScore(game: AstroddsGameScan, market: AstroddsMarketScan, riskWarnings: string[], missingData: string[]) {
  let score = 10;
  if (!market.matchReason) score -= 6;
  if (game.liveStatus === "FINAL") score = 0;
  if (market.betType === "TOTAL" && game.weather?.status !== "CONNECTED") score -= 4;
  if (!pitcherConnected(game) && (market.betType === "MONEYLINE" || market.betType === "TOTAL")) score -= 3;
  if (missingData.length >= 4) score -= 2;
  if (market.orderBook?.fillStatus && market.orderBook.fillStatus !== "OK") score -= 5;
  if (score <= 4) riskWarnings.push("Risk is elevated because key sources are missing or entry conditions are weak.");
  return clamp(score, 10);
}

export function analyzeMlbEdge(game: AstroddsGameScan, market: AstroddsMarketScan): AstroddsEdgeAssessment {
  const dataWarnings: string[] = [];
  const riskWarnings: string[] = [];
  const missingData: string[] = [];
  const probability = estimateMlbBetProbability(game, market);
  const sports = sportsMatchupScore(game, market, missingData, dataWarnings);
  const value = marketValueScore(market, probability, riskWarnings);
  const book = orderBookScore(market, riskWarnings);
  const risk = riskScore(game, market, riskWarnings, missingData);
  const wallet = walletScore(market.walletSupport?.rank);
  const edgeScore = clamp(sports + value + book + risk + wallet, 100);
  let decision = probability.decision;

  if (!market.matchReason || game.unmatchedReason || market.unmatchedReason) decision = "WAIT";
  if (!Number.isFinite(market.currentPrice)) decision = "WAIT";
  if (market.betType === "TOTAL" && game.weather?.status !== "CONNECTED" && (decision === "ELITE" || decision === "STRONG_BUY")) decision = "BUY";
  if (!market.orderBook && (decision === "ELITE" || decision === "STRONG_BUY")) decision = "BUY";
  if (market.orderBook?.status === "FAIR" && decision === "ELITE") decision = "STRONG_BUY";
  if (market.orderBook?.status === "POOR" && (decision === "BUY" || decision === "STRONG_BUY" || decision === "ELITE")) decision = "WATCH";
  if (market.orderBook?.status === "NO_LIQUIDITY" || (market.orderBook?.fillStatus && market.orderBook.fillStatus !== "OK")) decision = "WAIT";
  if (sports < 18 && (decision === "BUY" || decision === "STRONG_BUY" || decision === "ELITE")) decision = "WATCH";

  const confidence: AstroddsConfidence =
    decision === "ELITE"
      ? "ELITE"
      : decision === "STRONG_BUY"
        ? "STRONG"
        : decision === "BUY"
          ? "MEDIUM"
          : decision === "WATCH"
            ? "LOW"
            : "NO_BET";
  const reasons = [
    market.matchReason ? "Market is matched to a real MLB game." : "No clean MLB game market match.",
    `Model probability ${Math.round(probability.modelProbability * 100)}% vs market ${Math.round(probability.marketImpliedProbability * 100)}%.`,
    `Edge ${(probability.edge * 100).toFixed(1)}%.`,
    pitcherConnected(game) ? "Pitcher context is available." : "Pitcher data is partial.",
    game.weather?.status === "CONNECTED" ? "Weather is included." : "Weather is partial or missing.",
    probability.dataQuality === "HIGH" || probability.dataQuality === "MEDIUM" ? `Data quality is ${probability.dataQuality}.` : `Data quality is ${probability.dataQuality}, so this stays conservative.`,
    market.orderBook?.status === "EXCELLENT" || market.orderBook?.status === "GOOD"
      ? "Order book supports a clean $50 paper entry."
      : market.orderBook
        ? "Order book does not improve the signal."
        : "Order book is not connected.",
  ];

  return {
    edgeScore,
    decision,
    confidence,
    exactPick: exactPick(market),
    simpleWhy: [...probability.reasons, ...reasons].join(" "),
    dataWarnings: Array.from(new Set([...dataWarnings, ...probability.warnings.filter((warning) => warning.includes("source") || warning.includes("data"))])),
    riskWarnings: Array.from(new Set([...riskWarnings, ...probability.warnings])),
    missingData,
    recommendedAction: decision === "BUY" || decision === "STRONG_BUY" || decision === "ELITE" ? "Paper Trade 5%" : "WAIT",
    modelProbability: probability.modelProbability,
    marketImpliedProbability: probability.marketImpliedProbability,
    edge: probability.edge,
    expectedValue: probability.expectedValue,
    dataQuality: probability.dataQuality,
    sportsMatchupScore: sports,
    marketValueScore: value,
    orderBookScore: book,
    riskScore: risk,
    walletSupportScore: wallet,
  };
}
