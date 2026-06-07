import type {
  AstroddsConfidence,
  AstroddsDataQuality,
  AstroddsDecision,
  AstroddsGameScan,
  AstroddsMarketScan,
  AstroddsProbabilityAssessment,
} from "./types";

function clampProbability(value: number) {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0.01, Math.min(0.99, value));
}

function hasUsablePrice(price: number) {
  return Number.isFinite(price) && price > 0 && price < 1;
}

function pitcherConnected(game: AstroddsGameScan) {
  const text = game.keyPlayerStatus.toLowerCase();
  return Boolean(game.keyPlayerStatus && !text.includes("not posted") && !text.includes("not connected") && !text.includes("tbd"));
}

function sourceIsConnected(status?: string) {
  return status === "CONNECTED" || status === "PARTIAL";
}

function isHomePick(game: AstroddsGameScan, market: AstroddsMarketScan) {
  return Boolean(game.homeTeam && market.pick.toLowerCase().includes(game.homeTeam.toLowerCase()));
}

function orderBookQualityScore(market: AstroddsMarketScan) {
  if (!market.orderBook) return 0;
  if (market.orderBook.status === "EXCELLENT" || market.orderBook.status === "GOOD") return 20;
  if (market.orderBook.status === "FAIR") return 14;
  if (market.orderBook.status === "POOR") return 5;
  return 0;
}

function dataQualityFromScore(score: number): AstroddsDataQuality {
  if (score >= 80) return "HIGH";
  if (score >= 60) return "MEDIUM";
  if (score >= 35) return "LOW";
  return "VERY_LOW";
}

function confidenceFromDecision(decision: AstroddsDecision): AstroddsConfidence {
  if (decision === "ELITE") return "ELITE";
  if (decision === "STRONG_BUY") return "STRONG";
  if (decision === "BUY") return "MEDIUM";
  if (decision === "WATCH") return "LOW";
  return "NO_BET";
}

function capDecisionForWeakData(decision: AstroddsDecision, dataQuality: AstroddsDataQuality) {
  if (dataQuality === "VERY_LOW") return decision === "AVOID" ? "AVOID" : "WAIT";
  if (dataQuality === "LOW" && (decision === "ELITE" || decision === "STRONG_BUY" || decision === "BUY")) return "WATCH";
  return decision;
}

function capDecisionForOrderBook(decision: AstroddsDecision, market: AstroddsMarketScan) {
  if (!market.orderBook) {
    if (decision === "ELITE" || decision === "STRONG_BUY") return "BUY";
    return decision;
  }

  if (market.orderBook.status === "NO_LIQUIDITY" || market.orderBook.fillStatus === "NOT_ENOUGH_LIQUIDITY") return "WAIT";
  if (market.orderBook.status === "POOR" && (decision === "ELITE" || decision === "STRONG_BUY" || decision === "BUY")) return "WATCH";
  if (market.orderBook.status === "FAIR" && decision === "ELITE") return "STRONG_BUY";
  return decision;
}

function totalWeatherAdjustment(game: AstroddsGameScan, market: AstroddsMarketScan, reasons: string[], warnings: string[]) {
  if (market.betType !== "TOTAL") return 0;
  if (game.weather?.status !== "CONNECTED") {
    warnings.push("Weather is missing for this total, so no Strong Buy.");
    return 0;
  }

  const pick = market.pick.toLowerCase();
  const wind = game.weather.windMph ?? 0;
  const temperature = game.weather.temperatureF ?? 70;
  const precipitation = game.weather.precipitationProbability ?? 0;
  const under = pick.includes("under");
  const over = pick.includes("over");
  let adjustment = 0;

  if (under && wind <= 8 && precipitation < 35 && temperature < 78) {
    adjustment += 0.025;
    reasons.push("Weather is neutral to lower-scoring for an Under.");
  }
  if (under && precipitation >= 45) {
    adjustment += 0.015;
    warnings.push("Rain risk supports lower scoring but increases uncertainty.");
  }
  if (over && temperature >= 78) {
    adjustment += 0.018;
    reasons.push("Warm conditions give modest support to an Over.");
  }
  if (over && wind >= 12) {
    adjustment += 0.012;
    reasons.push("Wind speed adds modest Over support, but wind direction is not connected.");
  }
  if (over && precipitation >= 45) {
    adjustment -= 0.02;
    warnings.push("Rain risk conflicts with an Over.");
  }

  return adjustment;
}

function modelAdjustment(game: AstroddsGameScan, market: AstroddsMarketScan, reasons: string[], warnings: string[]) {
  let adjustment = 0;

  if (market.betType === "MONEYLINE") {
    if (pitcherConnected(game)) {
      reasons.push("Probable pitchers are posted, but pitcher performance stats are not connected yet.");
    } else {
      warnings.push("Pitcher data is missing or partial for this moneyline.");
    }

    if (isHomePick(game, market)) {
      adjustment += 0.012;
      reasons.push("Home-field context gives this side a small model boost.");
    }
  }

  if (market.betType === "SPREAD") {
    warnings.push("Run line has close-game risk and needs stronger team-form data.");
    if (pitcherConnected(game)) reasons.push("Probable pitchers are posted for the run line context.");
  }

  adjustment += totalWeatherAdjustment(game, market, reasons, warnings);

  if (!sourceIsConnected(game.lineups?.status)) warnings.push("Lineup source is not connected.");
  if (!sourceIsConnected(game.injuries?.status)) warnings.push("News/injury source is not connected.");
  warnings.push("Bullpen fatigue: NOT CONNECTED.");
  warnings.push("Team form: NOT CONNECTED.");
  warnings.push("Travel/rest: NOT CONNECTED.");

  return adjustment;
}

function dataQuality(game: AstroddsGameScan, market: AstroddsMarketScan, validPrice: boolean, warnings: string[]) {
  let score = 0;
  if (market.matchReason && !game.unmatchedReason && !market.unmatchedReason) score += 25;
  if (validPrice) score += 25;
  score += orderBookQualityScore(market);

  if (pitcherConnected(game)) score += market.betType === "MONEYLINE" || market.betType === "TOTAL" ? 15 : 9;
  else if (market.betType === "MONEYLINE" || market.betType === "TOTAL") warnings.push("Pitcher matchup is not fully connected.");

  if (market.betType === "TOTAL") {
    if (game.weather?.status === "CONNECTED") score += 15;
    else warnings.push("Weather source is required for high-quality MLB totals.");
  } else if (game.weather?.status === "CONNECTED") {
    score += 6;
  }

  if (sourceIsConnected(game.lineups?.status)) score += 4;
  if (sourceIsConnected(game.injuries?.status)) score += 4;

  return dataQualityFromScore(score);
}

function decide(input: {
  modelProbability: number;
  edge: number;
  dataQuality: AstroddsDataQuality;
  validPrice: boolean;
  market: AstroddsMarketScan;
}) {
  const { modelProbability, edge, dataQuality, validPrice, market } = input;

  if (!validPrice || !market.matchReason || market.unmatchedReason) return "WAIT" as AstroddsDecision;
  if (edge <= -0.03) return "AVOID" as AstroddsDecision;

  let decision: AstroddsDecision;
  const goodBook = market.orderBook?.status === "EXCELLENT" || market.orderBook?.status === "GOOD";
  const tradableBook = goodBook || market.orderBook?.status === "FAIR";

  if (edge >= 0.12 && modelProbability >= 0.62 && dataQuality === "HIGH" && goodBook) decision = "ELITE";
  else if (edge >= 0.08 && modelProbability >= 0.58 && (dataQuality === "HIGH" || dataQuality === "MEDIUM") && tradableBook) decision = "STRONG_BUY";
  else if (edge >= 0.05 && dataQuality !== "VERY_LOW" && tradableBook) decision = "BUY";
  else if (edge >= 0.02) decision = "WATCH";
  else decision = "WAIT";

  decision = capDecisionForWeakData(decision, dataQuality);
  decision = capDecisionForOrderBook(decision, market);

  if (market.betType === "TOTAL" && market.orderBook?.status !== "EXCELLENT" && market.orderBook?.status !== "GOOD" && decision === "STRONG_BUY") {
    decision = "BUY";
  }

  return decision;
}

export function estimateMlbBetProbability(game: AstroddsGameScan, market: AstroddsMarketScan): AstroddsProbabilityAssessment {
  const reasons: string[] = [];
  const warnings: string[] = [];
  const validPrice = hasUsablePrice(market.currentPrice);
  const marketImpliedProbability = validPrice ? market.currentPrice : 0;

  if (!validPrice) warnings.push("Missing Polymarket entry price.");
  if (!market.matchReason || game.unmatchedReason || market.unmatchedReason) warnings.push("Market is not cleanly matched to a single MLB game.");
  if (!market.orderBook) warnings.push("Order book is not connected, so Elite is disabled.");
  else if (market.orderBook.status === "POOR" || market.orderBook.status === "NO_LIQUIDITY") warnings.push("Order book is weak for a $50 paper entry.");

  const quality = dataQuality(game, market, validPrice, warnings);
  const prior = validPrice ? marketImpliedProbability : 0.5;
  const adjustment = modelAdjustment(game, market, reasons, warnings);
  const modelProbability = clampProbability(prior + adjustment);
  const edge = validPrice ? modelProbability - marketImpliedProbability : 0;
  const expectedValue = validPrice ? modelProbability / market.currentPrice - 1 : 0;
  const decision = decide({
    modelProbability,
    edge,
    dataQuality: quality,
    validPrice,
    market,
  });

  if (!reasons.length) reasons.push("Model stayed near market price because directional MLB data is limited.");
  if (edge < 0.02 && decision !== "AVOID") warnings.push("No meaningful model edge over the market price.");

  return {
    modelProbability,
    marketImpliedProbability,
    edge,
    expectedValue,
    dataQuality: quality,
    confidence: confidenceFromDecision(decision),
    decision,
    reasons,
    warnings: Array.from(new Set(warnings)),
  };
}
