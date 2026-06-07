import type { AstroddsConfidence, AstroddsDecision, AstroddsGameScan, AstroddsMarketScan } from "./types";
import { analyzeMlbEdge } from "./edge-engine";
import { scoreMarket, sportRiskNote } from "./scoring";

function confidenceFromScore(score: number): AstroddsConfidence {
  if (score >= 90) return "ELITE";
  if (score >= 82) return "STRONG";
  if (score >= 74) return "MEDIUM";
  if (score >= 60) return "LOW";
  return "NO_BET";
}

function baseDecision(score: number): AstroddsDecision {
  if (score >= 90) return "ELITE";
  if (score >= 82) return "STRONG_BUY";
  if (score >= 74) return "BUY";
  if (score >= 60) return "WATCH";
  if (score >= 48) return "WAIT";
  return "AVOID";
}

function cashoutDecision(market: AstroddsMarketScan): AstroddsDecision | undefined {
  if (!market.entryPrice) return undefined;
  const move = market.currentPrice - market.entryPrice;
  if (move >= 0.36) return "CASH_OUT";
  if (move >= 0.24) return "PROFIT_LOCK";
  if (move >= 0.16) return "HEDGE";
  return undefined;
}

function why(game: AstroddsGameScan, market: AstroddsMarketScan) {
  const score = market.score;
  const fragments = [
    `${market.pick} at ${market.currentPrice.toFixed(2)} is ${score?.entryQuality ?? "UNKNOWN"} entry quality.`,
    sportRiskNote(game.sport),
  ];

  if (game.weather?.summary) fragments.push(game.weather.summary);
  if (game.keyPlayerStatus) fragments.push(game.keyPlayerStatus);
  if (market.matchReason) fragments.push(`Match: ${market.matchReason}`);
  if (market.orderBook?.summary) fragments.push(market.orderBook.summary);
  if (market.unmatchedReason || game.unmatchedReason) fragments.push(`Unmatched reason: ${market.unmatchedReason ?? game.unmatchedReason}`);
  if (score?.missingDataWarnings.length) fragments.push(`Missing data: ${score.missingDataWarnings.join(" ")}`);
  if (market.walletSupport?.summary) fragments.push(`Wallet layer: ${market.walletSupport.summary}`);
  if (market.edge?.simpleWhy) fragments.push(`Edge: ${market.edge.simpleWhy}`);
  if (market.edge?.riskWarnings.length) fragments.push(`Risk: ${market.edge.riskWarnings.join(" ")}`);

  return fragments.join(" ");
}

export function applyDecisionEngine(games: AstroddsGameScan[]) {
  return games.map((game) => {
    const markets = game.markets.map((market) => {
      const edge = game.sport === "MLB" ? analyzeMlbEdge(game, market) : undefined;
      const rawScore = scoreMarket(game, market);
      const score = edge
        ? {
            sportsData: edge.sportsMatchupScore,
            marketPrice: edge.marketValueScore + edge.orderBookScore,
            liveGameState: 0,
            walletIntelligence: edge.walletSupportScore,
            riskManagement: edge.riskScore,
            total: edge.edgeScore,
            entryQuality: market.orderBook?.entryQuality ?? rawScore.entryQuality,
            missingDataWarnings: [...edge.dataWarnings, ...edge.riskWarnings, ...edge.missingData],
          }
        : rawScore;
      let decision = edge?.decision ?? cashoutDecision(market) ?? baseDecision(score.total);

      if (score.entryQuality === "NO_ENTRY") decision = "AVOID";
      if (score.entryQuality === "NO_LIQUIDITY") decision = "WAIT";
      if (score.entryQuality === "POOR") decision = "WATCH";
      if (score.entryQuality === "STRETCHED" && (decision === "BUY" || decision === "STRONG_BUY" || decision === "ELITE")) decision = "WATCH";
      if (score.sportsData < 28 && (decision === "STRONG_BUY" || decision === "ELITE")) decision = "WATCH";
      if (score.sportsData < 20 && (decision === "BUY" || decision === "STRONG_BUY" || decision === "ELITE")) decision = "WATCH";
      if ((market.walletSupport?.supportingWallets ?? 0) > 2 && score.sportsData < 20) decision = "WATCH";
      if (game.keyPlayerStatus.includes("MLB Data: NOT MATCHED") || game.source.includes("market-only")) decision = "WATCH";
      if (game.sport === "MLB" && market.betType === "TOTAL" && game.weather?.status !== "CONNECTED" && (decision === "STRONG_BUY" || decision === "ELITE")) decision = "WATCH";
      if (!market.orderBook && (decision === "STRONG_BUY" || decision === "ELITE")) decision = "BUY";
      if (market.orderBook?.status === "FAIR" && decision === "ELITE") decision = "STRONG_BUY";
      if (market.orderBook?.status === "POOR" && (decision === "BUY" || decision === "STRONG_BUY" || decision === "ELITE")) decision = "WATCH";
      if (market.orderBook?.status === "NO_LIQUIDITY") decision = "WAIT";
      if (market.orderBook?.fillStatus && market.orderBook.fillStatus !== "OK") decision = "WAIT";
      if (game.liveStatus === "FINAL") decision = "AVOID";

      let confidence = edge?.confidence ?? confidenceFromScore(score.total);
      if (decision === "ELITE") confidence = "ELITE";
      if (!market.orderBook && confidence === "ELITE") confidence = "STRONG";
      if ((market.orderBook?.status === "POOR" || market.orderBook?.status === "NO_LIQUIDITY") && (confidence === "ELITE" || confidence === "STRONG")) {
        confidence = "LOW";
      }
      if (decision === "WAIT" || decision === "AVOID") confidence = "NO_BET";
      const scoredMarket = {
        ...market,
        edge,
        probability: edge
          ? {
              modelProbability: edge.modelProbability,
              marketImpliedProbability: edge.marketImpliedProbability,
              edge: edge.edge,
              expectedValue: edge.expectedValue,
              dataQuality: edge.dataQuality,
              confidence: edge.confidence,
              decision: edge.decision,
              reasons: edge.simpleWhy ? [edge.simpleWhy] : [],
              warnings: [...edge.dataWarnings, ...edge.riskWarnings, ...edge.missingData],
            }
          : undefined,
        score,
        decision,
        confidence,
        why: why(game, { ...market, score }),
      };

      return scoredMarket;
    });

    return {
      ...game,
      markets,
    };
  });
}

export function rankedPicks(games: AstroddsGameScan[], limit = 5) {
  return games
    .flatMap((game) => game.markets.map((market) => ({ ...game, market })))
    .filter((entry) =>
      !entry.source.toLowerCase().includes("market-only") &&
      !entry.keyPlayerStatus.includes("MLB Data: NOT MATCHED") &&
      Boolean(entry.market.matchReason) &&
      !entry.market.unmatchedReason &&
      !entry.unmatchedReason &&
      (entry.market.decision === "BUY" || entry.market.decision === "STRONG_BUY" || entry.market.decision === "ELITE") &&
      entry.market.orderBook?.fillStatus === "OK" &&
      entry.market.orderBook.status !== "POOR" &&
      entry.market.orderBook.status !== "NO_LIQUIDITY",
    )
    .sort((a, b) => {
      const aScore = a.market.score;
      const bScore = b.market.score;

      return (
        (bScore?.total ?? 0) - (aScore?.total ?? 0) ||
        (bScore?.sportsData ?? 0) - (aScore?.sportsData ?? 0) ||
        (bScore?.marketPrice ?? 0) - (aScore?.marketPrice ?? 0) ||
        (b.market.liquidity ?? 0) - (a.market.liquidity ?? 0) ||
        (b.market.volume ?? 0) - (a.market.volume ?? 0) ||
        (b.market.walletSupport?.supportingWallets ?? 0) - (a.market.walletSupport?.supportingWallets ?? 0)
      );
    })
    .slice(0, limit);
}
