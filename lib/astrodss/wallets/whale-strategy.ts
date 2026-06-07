import { nextWhaleRescanAt } from "./known-wallets";
import type {
  CopyabilityStatus,
  HoldToResolutionLabel,
  LimitEntryDisciplineLabel,
  WalletActivity,
  WalletPosition,
  WalletProfile,
  WhalePositionCopyability,
  WhaleStrategyMetrics,
  WhaleWalletRank,
} from "./types";
import type { AstroddsOrderBookMetrics } from "../sports-data/types";

function avg(values: number[]) {
  const finite = values.filter((value) => Number.isFinite(value));
  return finite.length ? finite.reduce((total, value) => total + value, 0) / finite.length : undefined;
}

function positionVolume(position: WalletPosition) {
  if (typeof position.positionValue === "number") return Math.abs(position.positionValue);
  if (typeof position.shares === "number" && typeof position.avgEntryPrice === "number") return Math.abs(position.shares * position.avgEntryPrice);
  return 0;
}

function dedupeKey(position: WalletPosition) {
  return [
    position.handle,
    position.marketId ?? "",
    position.conditionId ?? "",
    position.assetId ?? "",
    position.side,
    position.outcome,
    position.avgEntryPrice?.toFixed(3) ?? "",
    position.createdAt?.slice(0, 13) ?? "",
  ].join("|");
}

export function dedupeWalletPositions(positions: WalletPosition[]) {
  const seen = new Set<string>();
  const deduped: WalletPosition[] = [];

  positions.forEach((position) => {
    const key = dedupeKey(position);
    if (seen.has(key)) return;
    seen.add(key);
    deduped.push(position);
  });

  return {
    positions: deduped,
    duplicatesRemoved: positions.length - deduped.length,
  };
}

function marketBreakdown(positions: WalletPosition[]) {
  return positions.reduce<Record<string, number>>((breakdown, position) => {
    breakdown[position.marketType] = (breakdown[position.marketType] ?? 0) + 1;
    return breakdown;
  }, {});
}

function dominantSport(positions: WalletPosition[]) {
  const counts = positions.reduce<Record<string, number>>((map, position) => {
    const sport = position.sport ?? "OTHER";
    map[sport] = (map[sport] ?? 0) + 1;
    return map;
  }, {});
  const total = positions.length || 1;
  const [sport, count] = Object.entries(counts).sort((a, b) => b[1] - a[1])[0] ?? ["OTHER", 0];

  return {
    sport,
    percent: Math.round((count / total) * 100),
  };
}

function inferLimitEntryDiscipline(positions: WalletPosition[], activity: WalletActivity[]): LimitEntryDisciplineLabel {
  const pricedPositions = positions.filter((position) => typeof position.avgEntryPrice === "number" && typeof position.currentPrice === "number");
  if (pricedPositions.length < 3 && activity.length < 5) return "UNKNOWN";

  const priceMovement = pricedPositions.map((position) => (position.currentPrice ?? 0) - (position.avgEntryPrice ?? 0));
  const favorable = priceMovement.filter((movement) => movement >= 0).length;
  const averageMovement = avg(priceMovement) ?? 0;

  if (favorable / Math.max(1, pricedPositions.length) >= 0.65 && averageMovement >= 0.01) return "DISCIPLINED_ENTRY";
  if (averageMovement <= -0.05) return "CHASES_PRICE";
  return "MIXED_ENTRY";
}

function inferHoldToResolution(positions: WalletPosition[]): HoldToResolutionLabel {
  const closed = positions.filter((position) => position.status === "CLOSED" || position.status === "WON" || position.status === "LOST" || position.status === "VOID");
  if (closed.length < 5) return "UNKNOWN";

  const resolved = closed.filter((position) => position.status === "WON" || position.status === "LOST" || position.status === "VOID" || Boolean(position.resolvedAt)).length;
  const heldRatio = resolved / closed.length;

  if (heldRatio >= 0.8) return "HOLDS_TO_RESOLUTION";
  if (heldRatio >= 0.45) return "MIXED_EXIT_AND_HOLD";
  return "ACTIVE_TRADER";
}

export function calculatePositionCopyability(
  position: WalletPosition,
  orderBook?: AstroddsOrderBookMetrics,
  now = new Date(),
): WhalePositionCopyability {
  const whaleAvgEntry = position.avgEntryPrice;
  const currentPrice = position.currentPrice ?? orderBook?.bestAsk;
  const delta =
    typeof whaleAvgEntry === "number" && typeof currentPrice === "number"
      ? currentPrice - whaleAvgEntry
      : undefined;
  const createdAt = position.createdAt ? new Date(position.createdAt) : undefined;
  const timeSinceWhaleEntryHours =
    createdAt && !Number.isNaN(createdAt.getTime())
      ? Math.max(0, (now.getTime() - createdAt.getTime()) / 36e5)
      : undefined;
  const enoughLiquidityForPaperTrade = orderBook ? orderBook.fillStatus === "OK" && orderBook.status !== "POOR" && orderBook.status !== "NO_LIQUIDITY" : true;
  let status: CopyabilityStatus = "UNKNOWN";
  let reason = "Not enough public price/order book data to judge copyability.";

  if (position.status !== "OPEN") {
    status = "UNKNOWN";
    reason = "Position is not open.";
  } else if (orderBook?.status === "NO_LIQUIDITY" || orderBook?.fillStatus === "NOT_ENOUGH_LIQUIDITY") {
    status = "NO_LIQUIDITY";
    reason = "Order book cannot fill a $50 paper trade.";
  } else if (typeof delta === "number") {
    if (delta <= 0.02) {
      status = "COPYABLE_NOW";
      reason = "Current price is within 2 cents of whale average entry.";
    } else if (delta <= 0.05) {
      status = "NEAR_WHALE_ENTRY";
      reason = "Current price is close to whale average entry.";
    } else if (delta <= 0.1) {
      status = "WATCH_ONLY";
      reason = "Price has moved away from whale entry; do not chase without model edge.";
    } else if (delta <= 0.18) {
      status = "STALE_ENTRY";
      reason = "Whale entry is stale relative to current price.";
    } else {
      status = "TOO_LATE";
      reason = "Current price is much worse than whale entry.";
    }
  }

  if (!enoughLiquidityForPaperTrade && status !== "NO_LIQUIDITY") {
    status = "WATCH_ONLY";
    reason = `${reason} Liquidity is not strong enough for a clean $50 entry.`;
  }

  return {
    positionId: position.id,
    handle: position.handle,
    marketTitle: position.marketTitle,
    side: position.side,
    whaleAvgEntry,
    currentPrice,
    currentBestAsk: orderBook?.bestAsk,
    spread: orderBook?.spread,
    enoughLiquidityForPaperTrade,
    priceDeltaFromWhaleEntry: delta,
    timeSinceWhaleEntryHours,
    status,
    reason,
  };
}

function overallCopyability(copyability: WhalePositionCopyability[]): CopyabilityStatus {
  if (copyability.some((entry) => entry.status === "COPYABLE_NOW")) return "COPYABLE_NOW";
  if (copyability.some((entry) => entry.status === "NEAR_WHALE_ENTRY")) return "NEAR_WHALE_ENTRY";
  if (copyability.some((entry) => entry.status === "WATCH_ONLY")) return "WATCH_ONLY";
  if (copyability.some((entry) => entry.status === "STALE_ENTRY")) return "STALE_ENTRY";
  if (copyability.some((entry) => entry.status === "TOO_LATE")) return "TOO_LATE";
  if (copyability.some((entry) => entry.status === "NO_LIQUIDITY")) return "NO_LIQUIDITY";
  return "UNKNOWN";
}

export function calculateWhaleStrategy(profile: WalletProfile, rank: WhaleWalletRank = "WHALE_WATCH"): WhaleStrategyMetrics {
  const scannedAt = new Date();
  const { positions, duplicatesRemoved } = dedupeWalletPositions([...profile.openPositions, ...profile.closedPositions]);
  const resolvedWins = positions.filter((position) => position.status === "WON").length;
  const resolvedLosses = positions.filter((position) => position.status === "LOST").length;
  const voids = positions.filter((position) => position.status === "VOID").length;
  const open = positions.filter((position) => position.status === "OPEN");
  const closed = positions.filter((position) => position.status !== "OPEN");
  const settled = resolvedWins + resolvedLosses;
  const totalVolume = positions.reduce((total, position) => total + positionVolume(position), 0);
  const pnl = positions.reduce((total, position) => total + (position.realizedPnl ?? 0), 0);
  const dominant = dominantSport(positions);
  const nonFutures = positions.filter((position) => position.marketType !== "FUTURE").length;
  const copyability = open.map((position) => calculatePositionCopyability(position));

  return {
    handle: profile.handle,
    totalPositions: positions.length,
    openPositions: open.length,
    closedPositions: closed.length,
    resolvedWins,
    resolvedLosses,
    voids,
    pendingPositions: positions.filter((position) => position.status === "OPEN" || position.status === "UNKNOWN").length,
    winRate: settled ? resolvedWins / settled : 0,
    roi: totalVolume ? pnl / totalVolume : 0,
    totalVolume,
    averageBetSize: positions.length ? totalVolume / positions.length : 0,
    biggestBet: Math.max(0, ...positions.map(positionVolume)),
    sportFocusPercent: dominant.percent,
    sportFocus: dominant.sport,
    singleGameRatio: positions.length ? nonFutures / positions.length : 0,
    futuresRatio: positions.length ? 1 - nonFutures / positions.length : 0,
    marketTypeBreakdown: marketBreakdown(positions),
    averageEntryPrice: avg(positions.map((position) => position.avgEntryPrice ?? Number.NaN)),
    averageCurrentPrice: avg(positions.map((position) => position.currentPrice ?? Number.NaN)),
    averagePriceMovementAfterEntry: avg(positions.map((position) =>
      typeof position.avgEntryPrice === "number" && typeof position.currentPrice === "number"
        ? position.currentPrice - position.avgEntryPrice
        : Number.NaN,
    )),
    averageHoldingTimeHours: avg(positions.map((position) => {
      const start = position.createdAt ? new Date(position.createdAt).getTime() : Number.NaN;
      const end = position.resolvedAt || position.updatedAt ? new Date(position.resolvedAt ?? position.updatedAt ?? "").getTime() : Number.NaN;
      return Number.isFinite(start) && Number.isFinite(end) ? (end - start) / 36e5 : Number.NaN;
    })),
    duplicateTradesRemoved: duplicatesRemoved,
    limitEntryDiscipline: inferLimitEntryDiscipline(positions, profile.activity),
    holdToResolution: inferHoldToResolution(positions),
    copyabilityScore: overallCopyability(copyability),
    lastScanned: scannedAt.toISOString(),
    nextRescan: nextWhaleRescanAt(rank, open.some((position) => position.sport && position.sport !== "OTHER")),
  };
}
