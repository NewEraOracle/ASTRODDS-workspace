import { buildMlbGameStatusValidation, type MLBGameStatusSnapshot, type MLBGameStatusValidation } from "./mlb/game-status-validation";
import { calculateMLBLineupImpact, type MLBLineupImpact } from "./mlb/lineup-impact";
import { compactId } from "./sports-data/normalize";
import type {
  AstroddsDataQuality,
  AstroddsDecision,
  AstroddsGameScan,
  AstroddsMarketScan,
} from "./sports-data/types";
import { consensusForMarket } from "./wallets/whale-consensus";
import type { CopyabilityStatus, WhaleConsensusSignal } from "./wallets/types";

export type UnifiedSignalDecision = "ELITE" | "STRONG_BUY" | "BUY" | "WATCH" | "WAIT" | "AVOID";

export type UnifiedWhaleSupport =
  | "NONE"
  | "SINGLE_WHALE_ACTIVITY"
  | "COPYABLE_WHALE"
  | "MULTI_WHALE_CONFIRMATION"
  | "DIAMOND_CONSENSUS"
  | "STALE_ENTRY"
  | "CONFLICT";

export type UnifiedSignalType =
  | "MODEL_ONLY"
  | "WHALE_ONLY_WATCH"
  | "WHALE_CONFIRMED"
  | "MULTI_WHALE_CONFIRMED"
  | "MODEL_WHALE_ORDERBOOK_ALIGNED"
  | "DATA_ONLY";

export type UnifiedAstroddsSignal = {
  signalId: string;
  sport: string;
  game: string;
  gameId?: string;
  marketId?: string;
  conditionId?: string;
  assetId?: string;
  marketType: string;
  pick: string;
  entryPrice?: number;
  modelProbability?: number;
  marketProbability?: number;
  edge?: number;
  expectedValue?: number;
  dataQuality: AstroddsDataQuality | "DATA_ONLY";
  lineupImpact: MLBLineupImpact;
  gameStatusValidation?: MLBGameStatusValidation;
  mlbStatus?: MLBGameStatusSnapshot;
  gameStatusBlockReasons: string[];
  orderBookQuality: string;
  whaleSupport: UnifiedWhaleSupport;
  copyability: string;
  confidence: string;
  decision: UnifiedSignalDecision;
  why: string[];
  warnings: string[];
  telegramEligible: boolean;
  paperTradeEligible: boolean;
  signalType: UnifiedSignalType;
  gameRef?: AstroddsGameScan;
  marketRef?: AstroddsMarketScan;
  whaleConsensus?: WhaleConsensusSignal;
};

export type BuildUnifiedSignalsOptions = {
  whaleConsensus?: WhaleConsensusSignal[];
  telegramSignalsEnabled?: boolean;
  telegramWhaleAlertsEnabled?: boolean;
};

const decisionRank: Record<UnifiedSignalDecision, number> = {
  AVOID: 0,
  WAIT: 1,
  WATCH: 2,
  BUY: 3,
  STRONG_BUY: 4,
  ELITE: 5,
};

const allowedMarketDecisions = new Set<AstroddsDecision>(["ELITE", "STRONG_BUY", "BUY", "WATCH", "WAIT", "AVOID"]);
const futuresKeywords = [
  "world series",
  "championship",
  "division winner",
  "make playoffs",
  "mvp",
  "cy young",
  "season win",
  "stanley cup",
  "nba finals",
  "super bowl",
  "crypto",
  "bitcoin",
  "ipo",
  "election",
];

function hasUsablePrice(price?: number) {
  return typeof price === "number" && Number.isFinite(price) && price > 0 && price < 1;
}

function uniqueStrings(values: Array<string | undefined | null>) {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value))));
}

function marketTypeLabel(market?: AstroddsMarketScan) {
  if (!market) return "Not Matched";
  if (market.betType === "MONEYLINE") return "Moneyline";
  if (market.betType === "SPREAD") return "Run Line";
  if (market.betType === "TOTAL") return "Over Under";
  if (market.betType === "PROP") return "Prop";
  return "Other";
}

function orderBookQuality(market?: AstroddsMarketScan) {
  if (!market) return "WAITING_FOR_MATCHED_POLYMARKET_TOKEN";
  if (!market.assetId) return "NO_CLOB_TOKEN_ID";
  return market.orderBook?.status ?? "NOT_CONNECTED";
}

function orderBookAcceptable(status: string) {
  return status === "EXCELLENT" || status === "GOOD" || status === "FAIR";
}

function orderBookBad(status: string) {
  return status === "POOR" || status === "NO_LIQUIDITY";
}

function dataQuality(market?: AstroddsMarketScan): AstroddsDataQuality | "DATA_ONLY" {
  if (!market) return "DATA_ONLY";
  return market.probability?.dataQuality ?? market.edge?.dataQuality ?? "VERY_LOW";
}

function confidenceFromDecision(decision: UnifiedSignalDecision) {
  if (decision === "ELITE") return "Elite";
  if (decision === "STRONG_BUY") return "Strong";
  if (decision === "BUY") return "Medium";
  if (decision === "WATCH") return "Low";
  return "No Bet";
}

function confidence(market: AstroddsMarketScan | undefined, decision: UnifiedSignalDecision) {
  return market?.confidence?.replace(/_/g, " ") ?? confidenceFromDecision(decision);
}

function isFuturesOrWrongMarket(market: AstroddsMarketScan) {
  const text = `${market.marketTitle} ${market.category ?? ""}`.toLowerCase();
  return futuresKeywords.some((keyword) => text.includes(keyword));
}

function buildGameStatusValidation(game: AstroddsGameScan, market?: AstroddsMarketScan) {
  return game.gameStatusValidation ?? buildMlbGameStatusValidation({
    gameId: game.id,
    game: game.game,
    startTime: game.startTime,
    marketDate: market?.marketDate ?? market?.gameDate ?? game.startTime,
    liveStatus: game.liveStatus,
    mlbStatus: game.mlbStatus,
    marketTitle: market?.marketTitle ?? game.game,
    marketPick: market?.pick,
  });
}

function blockedByGameStatus(validation: MLBGameStatusValidation): UnifiedSignalDecision {
  if (validation.isGameActiveForBetting) return "WAIT";
  if (validation.isPostponed || validation.isSuspended || validation.isCancelled || validation.isFinal || validation.isLive) return "AVOID";
  return "WAIT";
}

function mappedMarketDecision(decision?: AstroddsDecision): UnifiedSignalDecision | undefined {
  return decision && allowedMarketDecisions.has(decision) ? (decision as UnifiedSignalDecision) : undefined;
}

function capDecision(current: UnifiedSignalDecision, cap?: UnifiedSignalDecision) {
  if (!cap) return current;
  return decisionRank[current] > decisionRank[cap] ? cap : current;
}

function whaleSupportFor(consensus?: WhaleConsensusSignal): UnifiedWhaleSupport {
  if (!consensus) return "NONE";
  if (consensus.consensusStrength === "CONFLICTED_WHALES" || consensus.copyabilityStatus === "CONFLICT") return "CONFLICT";
  if (consensus.copyabilityStatus === "STALE_ENTRY" || consensus.copyabilityStatus === "TOO_LATE" || consensus.consensusStrength === "STALE_CONSENSUS") {
    return "STALE_ENTRY";
  }
  if (consensus.consensusStrength === "DIAMOND_CONSENSUS") return "DIAMOND_CONSENSUS";
  if (consensus.consensusStrength === "MULTI_WHALE_CONFIRMATION") return "MULTI_WHALE_CONFIRMATION";
  if (consensus.copyabilityStatus === "COPYABLE_NOW" || consensus.copyabilityStatus === "NEAR_WHALE_ENTRY") return "COPYABLE_WHALE";
  return "SINGLE_WHALE_ACTIVITY";
}

function whaleCopyable(copyability?: CopyabilityStatus) {
  return copyability === "COPYABLE_NOW" || copyability === "NEAR_WHALE_ENTRY";
}

function whaleConfirms(support: UnifiedWhaleSupport, consensus?: WhaleConsensusSignal) {
  return (
    Boolean(consensus) &&
    support !== "NONE" &&
    support !== "CONFLICT" &&
    support !== "STALE_ENTRY" &&
    whaleCopyable(consensus?.copyabilityStatus)
  );
}

function signalType(input: {
  market?: AstroddsMarketScan;
  decision: UnifiedSignalDecision;
  support: UnifiedWhaleSupport;
  consensus?: WhaleConsensusSignal;
  edge?: number;
  bookAcceptable: boolean;
}): UnifiedSignalType {
  if (!input.market) return "DATA_ONLY";
  if (input.market.gameStatusValidation && !input.market.gameStatusValidation.isGameActiveForBetting) return "DATA_ONLY";
  if (input.support === "CONFLICT" || input.support === "STALE_ENTRY") return "WHALE_ONLY_WATCH";
  if (input.support === "NONE") return "MODEL_ONLY";
  if ((input.edge ?? 0) <= 0 || input.decision === "WATCH" || input.decision === "WAIT" || input.decision === "AVOID") return "WHALE_ONLY_WATCH";
  if (input.bookAcceptable && whaleConfirms(input.support, input.consensus) && decisionRank[input.decision] >= decisionRank.BUY) {
    return "MODEL_WHALE_ORDERBOOK_ALIGNED";
  }
  if (input.support === "DIAMOND_CONSENSUS" || input.support === "MULTI_WHALE_CONFIRMATION") return "MULTI_WHALE_CONFIRMED";
  return "WHALE_CONFIRMED";
}

function exactPick(market?: AstroddsMarketScan, validation?: MLBGameStatusValidation) {
  if (validation && !validation.isGameActiveForBetting) return "No bet - MLB game status blocked";
  if (!market) return "--";
  if (market.edge?.exactPick) return market.edge.exactPick;
  const price = hasUsablePrice(market.currentPrice) ? market.currentPrice.toFixed(2) : "--";
  if (market.betType === "MONEYLINE") return `Bet ${market.pick} Moneyline at ${price}`;
  if (market.betType === "SPREAD") return `Bet ${market.pick} Run Line at ${price}`;
  if (market.betType === "TOTAL") return `Bet ${market.pick} at ${price}`;
  return `Bet ${market.pick} at ${price}`;
}

function deriveDecision(input: {
  market?: AstroddsMarketScan;
  dataQuality: AstroddsDataQuality | "DATA_ONLY";
  bookQuality: string;
  support: UnifiedWhaleSupport;
  lineupImpact: MLBLineupImpact;
  gameStatusValidation?: MLBGameStatusValidation;
}) {
  const { market, dataQuality: quality, bookQuality, support, lineupImpact, gameStatusValidation } = input;
  if (gameStatusValidation && !gameStatusValidation.isGameActiveForBetting) {
    return blockedByGameStatus(gameStatusValidation);
  }
  if (!market) return "WAIT" as UnifiedSignalDecision;
  if (isFuturesOrWrongMarket(market)) return "AVOID" as UnifiedSignalDecision;
  if (!market.matchReason || market.unmatchedReason || !hasUsablePrice(market.currentPrice)) return "WAIT" as UnifiedSignalDecision;

  const modelProbability = market.probability?.modelProbability ?? market.edge?.modelProbability;
  const edge = market.probability?.edge ?? market.edge?.edge;
  if (typeof edge !== "number" || typeof modelProbability !== "number") return support === "NONE" ? "WAIT" : "WATCH";
  if (edge < 0) return "AVOID";
  if (support === "CONFLICT") return edge >= 0.05 ? "WATCH" : "AVOID";
  if (support === "STALE_ENTRY") return "WAIT";
  if (orderBookBad(bookQuality)) return edge >= 0.02 ? "WATCH" : "WAIT";
  if (bookQuality === "NOT_CONNECTED" || bookQuality === "NO_CLOB_TOKEN_ID") return edge >= 0.05 ? "WATCH" : "WAIT";

  const bookOk = orderBookAcceptable(bookQuality);
  const highQuality = quality === "HIGH";
  const usableQuality = quality === "HIGH" || quality === "MEDIUM";
  let decision: UnifiedSignalDecision = "WAIT";

  if (edge >= 0.12 && modelProbability >= 0.62 && highQuality && (bookQuality === "EXCELLENT" || bookQuality === "GOOD")) decision = "ELITE";
  else if (edge >= 0.08 && modelProbability >= 0.58 && usableQuality && bookOk) decision = "STRONG_BUY";
  else if (edge >= 0.05 && usableQuality && bookOk) decision = "BUY";
  else if (edge >= 0.02 || support !== "NONE") decision = "WATCH";

  const existing = mappedMarketDecision(market.decision);
  if (existing && support !== "COPYABLE_WHALE" && support !== "MULTI_WHALE_CONFIRMATION" && support !== "DIAMOND_CONSENSUS") {
    decision = capDecision(decision, existing);
  } else if (existing && decisionRank[existing] <= decisionRank.WATCH && decisionRank[decision] > decisionRank.BUY) {
    decision = "BUY";
  }

  if (lineupImpact.lineupStatus === "confirmed" && lineupImpact.lineupImpactScore >= 0.74 && decision === "BUY" && edge >= 0.08 && modelProbability >= 0.58 && usableQuality && bookOk) {
    decision = "STRONG_BUY";
  }
  if (lineupImpact.lineupStatus === "projected" && decision === "ELITE") decision = "STRONG_BUY";
  if (lineupImpact.lineupStatus === "missing" && decisionRank[decision] > decisionRank.WATCH) decision = "WATCH";
  if (lineupImpact.lineupImpactScore < 0.45 && decisionRank[decision] > decisionRank.WATCH) decision = "WATCH";
  if (quality === "LOW" && decisionRank[decision] > decisionRank.WATCH) decision = "WATCH";
  if (quality === "VERY_LOW" && decision !== "AVOID") decision = "WAIT";
  return decision;
}

function whyLines(
  game: AstroddsGameScan,
  market: AstroddsMarketScan | undefined,
  consensus: WhaleConsensusSignal | undefined,
  decision: UnifiedSignalDecision,
  lineupImpact: MLBLineupImpact,
  validation?: MLBGameStatusValidation,
) {
  if (!market) {
    return uniqueStrings([
      ...(validation && !validation.isGameActiveForBetting ? validation.gameStatusBlockReasons : []),
      "Real MLB game found, but no matching Polymarket single-game market was found.",
      "ASTRODDS is in MLB DATA ONLY mode for this row.",
      "Best action is WAIT until a clean price and token are available.",
    ]);
  }

  const lines = [
    ...(validation && !validation.isGameActiveForBetting ? validation.gameStatusBlockReasons : []),
    market.edge
      ? `Model probability ${Math.round(market.edge.modelProbability * 100)}% vs market ${Math.round(market.edge.marketImpliedProbability * 100)}%; edge ${(market.edge.edge * 100).toFixed(1)}%.`
      : market.probability
        ? `Model probability ${Math.round(market.probability.modelProbability * 100)}% vs market ${Math.round(market.probability.marketImpliedProbability * 100)}%; edge ${(market.probability.edge * 100).toFixed(1)}%.`
        : "Model probability is not available yet.",
    market.matchReason ? "Market is matched to a real MLB game." : "Market is not cleanly matched.",
  ];

  if (market.edge?.simpleWhy) lines.push(market.edge.simpleWhy);
  else if (market.probability?.reasons.length) lines.push(market.probability.reasons.slice(0, 2).join(" "));
  if (market.orderBook?.status === "EXCELLENT" || market.orderBook?.status === "GOOD") lines.push("Order book supports a clean $50 paper entry.");
  else if (market.orderBook?.status === "FAIR") lines.push("Order book is fair, so sizing stays paper-only.");
  else if (market.orderBook) lines.push("Order book does not support an aggressive entry.");
  else lines.push("Order book is not connected, so Elite is disabled.");
  if (lineupImpact.lineupStatus === "confirmed") lines.push("Lineup is confirmed and included as a supporting model factor.");
  else if (lineupImpact.lineupStatus === "projected") lines.push("Lineup is projected only, so confidence stays conservative.");
  else lines.push("Lineup data unavailable; official pick eligibility is downgraded.");
  if (consensus) {
    lines.push(`Whale support: ${consensus.walletsOnSameSide.join(", ")} ${consensus.copyabilityStatus}.`);
  }
  if (decision === "WAIT") lines.push("No clear value entry yet; WAIT is the correct action.");

  return Array.from(new Set(lines)).slice(0, 6);
}

function warningLines(game: AstroddsGameScan, market: AstroddsMarketScan | undefined, support: UnifiedWhaleSupport, validation?: MLBGameStatusValidation) {
  const warnings = new Set<string>();
  validation?.warnings.forEach((warning) => warnings.add(warning));
  if (!market) {
    warnings.add("Missing Polymarket price and order book.");
    return Array.from(warnings);
  }

  market.probability?.warnings.forEach((warning) => warnings.add(warning));
  market.edge?.dataWarnings.forEach((warning) => warnings.add(warning));
  market.edge?.riskWarnings.forEach((warning) => warnings.add(warning));
  if (support === "STALE_ENTRY") warnings.add("Whale entry is stale; do not chase.");
  if (support === "CONFLICT") warnings.add("Whale activity conflicts with this side.");
  if (!market.orderBook) warnings.add("Order book not connected; Elite disabled.");
  if (market.orderBook?.status === "POOR" || market.orderBook?.status === "NO_LIQUIDITY") warnings.add("Bad order book blocks BUY/STRONG BUY.");
  if (market.betType === "TOTAL" && game.weather?.status !== "CONNECTED") warnings.add("Weather missing for MLB total; no Strong Buy.");
  const lineupImpact = calculateMLBLineupImpact(game, market);
  lineupImpact.downgradeReasons.forEach((reason) => warnings.add(reason));

  return Array.from(warnings);
}

export function buildUnifiedSignal(
  game: AstroddsGameScan,
  market?: AstroddsMarketScan,
  options: BuildUnifiedSignalsOptions = {},
): UnifiedAstroddsSignal {
  const consensus = market ? consensusForMarket(market, options.whaleConsensus ?? []) : undefined;
  const support = whaleSupportFor(consensus);
  const gameStatusValidation = buildGameStatusValidation(game, market);
  const lineupImpact = calculateMLBLineupImpact(game, market);
  const bookQuality = orderBookQuality(market);
  const quality = dataQuality(market);
  const decision = deriveDecision({ market, dataQuality: quality, bookQuality, support, lineupImpact, gameStatusValidation });
  const edge = market?.probability?.edge ?? market?.edge?.edge;
  const modelProbability = market?.probability?.modelProbability ?? market?.edge?.modelProbability;
  const marketProbability = market?.probability?.marketImpliedProbability ?? market?.edge?.marketImpliedProbability;
  const bookOk = orderBookAcceptable(bookQuality);
  const signal = signalType({
    market,
    decision,
    support,
    consensus,
    edge,
    bookAcceptable: bookOk,
  });
  const warnings = warningLines(game, market, support, gameStatusValidation);
  const blockedReasons = gameStatusValidation.gameStatusBlockReasons;
  const telegramEligible =
    Boolean(options.telegramSignalsEnabled && options.telegramWhaleAlertsEnabled) &&
    (decision === "ELITE" || decision === "STRONG_BUY") &&
    bookOk &&
    support !== "STALE_ENTRY" &&
    support !== "CONFLICT" &&
    gameStatusValidation.isGameActiveForBetting &&
    lineupImpact.lineupStatus !== "missing" &&
    (whaleConfirms(support, consensus) || (edge ?? 0) >= 0.12);
  const paperTradeEligible =
    Boolean(market) &&
    (decision === "ELITE" || decision === "STRONG_BUY" || decision === "BUY") &&
    hasUsablePrice(market?.currentPrice) &&
    bookOk &&
    quality !== "LOW" &&
    quality !== "VERY_LOW" &&
    gameStatusValidation.isGameActiveForBetting &&
    lineupImpact.lineupStatus !== "missing" &&
    lineupImpact.lineupImpactScore >= 0.5 &&
    support !== "STALE_ENTRY" &&
    support !== "CONFLICT" &&
    (edge ?? 0) >= 0.05;
  const idParts = [game.sport, game.id, market?.marketId ?? "data-only", market?.assetId ?? market?.pick ?? "wait"];

  return {
    signalId: compactId(idParts.join(" ")),
    sport: game.sport,
    game: game.game,
    gameId: game.id,
    marketId: market?.marketId,
    conditionId: market?.conditionId,
    assetId: market?.assetId,
    marketType: marketTypeLabel(market),
    pick: exactPick(market, gameStatusValidation),
    entryPrice: hasUsablePrice(market?.currentPrice) ? market?.currentPrice : undefined,
    modelProbability,
    marketProbability,
    edge,
    expectedValue: market?.probability?.expectedValue ?? market?.edge?.expectedValue,
    dataQuality: quality,
    gameStatusValidation,
    mlbStatus: game.mlbStatus,
    gameStatusBlockReasons: blockedReasons,
    orderBookQuality: bookQuality,
    lineupImpact,
    whaleSupport: support,
    copyability: consensus?.copyabilityStatus ?? "NONE",
    confidence: confidence(market, decision),
    decision,
    why: whyLines(game, market, consensus, decision, lineupImpact, gameStatusValidation),
    warnings,
    telegramEligible,
    paperTradeEligible,
    signalType: signal,
    gameRef: game,
    marketRef: market,
    whaleConsensus: consensus,
  };
}

export function buildUnifiedSignals(games: AstroddsGameScan[], options: BuildUnifiedSignalsOptions = {}) {
  const signals = games
    .filter((game) => game.sport === "MLB" && !game.source.toLowerCase().includes("market-only"))
    .flatMap((game) => {
      if (!game.markets.length) return [buildUnifiedSignal(game, undefined, options)];
      return game.markets.map((market) => buildUnifiedSignal(game, market, options));
    });

  return signals.sort((a, b) => {
    const aEdge = a.edge ?? -1;
    const bEdge = b.edge ?? -1;
    return (
      decisionRank[b.decision] - decisionRank[a.decision] ||
      Number(b.paperTradeEligible) - Number(a.paperTradeEligible) ||
      bEdge - aEdge ||
      (b.modelProbability ?? 0) - (a.modelProbability ?? 0)
    );
  });
}

export function serializeUnifiedSignal(signal: UnifiedAstroddsSignal) {
  return {
    signalId: signal.signalId,
    sport: signal.sport,
    game: signal.game,
    gameId: signal.gameId,
    marketId: signal.marketId,
    conditionId: signal.conditionId,
    assetId: signal.assetId,
    marketType: signal.marketType,
    pick: signal.pick,
    entryPrice: signal.entryPrice,
    modelProbability: signal.modelProbability,
    marketProbability: signal.marketProbability,
    edge: signal.edge,
    expectedValue: signal.expectedValue,
    dataQuality: signal.dataQuality,
    gameStatusValidation: signal.gameStatusValidation,
    mlbStatus: signal.mlbStatus,
    gameStatusBlockReasons: signal.gameStatusBlockReasons,
    orderBookQuality: signal.orderBookQuality,
    lineupImpact: signal.lineupImpact,
    whaleSupport: signal.whaleSupport,
    copyability: signal.copyability,
    confidence: signal.confidence,
    decision: signal.decision,
    why: signal.why,
    warnings: signal.warnings,
    telegramEligible: signal.telegramEligible,
    paperTradeEligible: signal.paperTradeEligible,
    signalType: signal.signalType,
  };
}
