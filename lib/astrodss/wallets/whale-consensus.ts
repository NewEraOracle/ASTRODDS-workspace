import { normalizeText } from "../sports-data/normalize";
import type { AstroddsMarketScan } from "../sports-data/types";
import { calculatePositionCopyability } from "./whale-strategy";
import type {
  CopyabilityStatus,
  WalletPosition,
  WalletProfile,
  WhaleConsensusLabel,
  WhaleConsensusSignal,
  WhaleSignalType,
} from "./types";

function consensusKey(position: WalletPosition) {
  return [
    position.marketId ?? position.conditionId ?? normalizeText(position.marketTitle),
    normalizeText(position.side || position.outcome),
  ].join("|");
}

function oppositeKey(position: WalletPosition) {
  return position.marketId ?? position.conditionId ?? normalizeText(position.marketTitle);
}

function copyabilityRank(status: CopyabilityStatus) {
  const ranks: Record<CopyabilityStatus, number> = {
    COPYABLE_NOW: 7,
    NEAR_WHALE_ENTRY: 6,
    WATCH_ONLY: 5,
    STALE_ENTRY: 4,
    TOO_LATE: 3,
    NO_LIQUIDITY: 2,
    CONFLICT: 1,
    UNKNOWN: 0,
  };
  return ranks[status];
}

function bestCopyability(statuses: CopyabilityStatus[]) {
  return statuses.sort((a, b) => copyabilityRank(b) - copyabilityRank(a))[0] ?? "UNKNOWN";
}

function consensusStrength(walletsOnSameSide: number, walletsOnOppositeSide: number, copyability: CopyabilityStatus): WhaleConsensusLabel {
  if (walletsOnSameSide === 0) return "NO_WHALE_SIGNAL";
  if (walletsOnOppositeSide > 0 && walletsOnOppositeSide >= walletsOnSameSide) return "CONFLICTED_WHALES";
  if (copyability === "STALE_ENTRY" || copyability === "TOO_LATE") return "STALE_CONSENSUS";
  if (walletsOnSameSide >= 3 && copyability === "COPYABLE_NOW") return "DIAMOND_CONSENSUS";
  if (walletsOnSameSide >= 2) return "MULTI_WHALE_CONFIRMATION";
  return "SINGLE_WHALE_ACTIVITY";
}

function signalType(strength: WhaleConsensusLabel, copyability: CopyabilityStatus): WhaleSignalType {
  if (strength === "CONFLICTED_WHALES") return "CONFLICT";
  if (copyability === "STALE_ENTRY" || copyability === "TOO_LATE") return "STALE_WHALE_ENTRY";
  if (strength === "DIAMOND_CONSENSUS" || strength === "MULTI_WHALE_CONFIRMATION") return "MULTI_WHALE_CONFIRMED";
  if (strength === "SINGLE_WHALE_ACTIVITY") return "WHALE_CONFIRMED";
  return "MODEL_ONLY";
}

function priceAverage(positions: WalletPosition[]) {
  const priced = positions.map((position) => position.avgEntryPrice).filter((price): price is number => typeof price === "number");
  return priced.length ? priced.reduce((total, price) => total + price, 0) / priced.length : undefined;
}

function currentPriceAverage(positions: WalletPosition[]) {
  const priced = positions.map((position) => position.currentPrice).filter((price): price is number => typeof price === "number");
  return priced.length ? priced.reduce((total, price) => total + price, 0) / priced.length : undefined;
}

export function buildWhaleConsensus(profiles: WalletProfile[], sport?: string): WhaleConsensusSignal[] {
  const openPositions = profiles.flatMap((profile) =>
    profile.openPositions.filter((position) => {
      if (position.status !== "OPEN") return false;
      if (!sport) return true;
      return normalizeText(position.sport) === normalizeText(sport);
    }),
  );
  const byMarket = new Map<string, WalletPosition[]>();

  openPositions.forEach((position) => {
    const key = consensusKey(position);
    byMarket.set(key, [...(byMarket.get(key) ?? []), position]);
  });

  return Array.from(byMarket.entries()).map(([key, positions]) => {
    const first = positions[0];
    const marketScope = oppositeKey(first);
    const opposite = openPositions.filter((position) => oppositeKey(position) === marketScope && consensusKey(position) !== key);
    const averageWhaleEntry = priceAverage(positions);
    const currentPrice = currentPriceAverage(positions);
    const copyabilityStatuses = positions.map((position) => calculatePositionCopyability(position).status);
    const copyabilityStatus = bestCopyability(copyabilityStatuses);
    const strength = consensusStrength(positions.length, opposite.length, copyabilityStatus);

    return {
      id: key,
      sport: first.sport,
      marketTitle: first.marketTitle,
      marketId: first.marketId,
      conditionId: first.conditionId,
      assetId: first.assetId,
      side: first.side,
      walletsOnSameSide: Array.from(new Set(positions.map((position) => position.handle))),
      walletsOnOppositeSide: Array.from(new Set(opposite.map((position) => position.handle))),
      totalWhalePositionValue: positions.reduce((total, position) => total + (position.positionValue ?? 0), 0),
      averageWhaleEntry,
      currentPrice,
      priceDeltaFromWhaleAverage:
        typeof averageWhaleEntry === "number" && typeof currentPrice === "number" ? currentPrice - averageWhaleEntry : undefined,
      consensusStrength: strength,
      conflictingWhales: Array.from(new Set(opposite.map((position) => position.handle))),
      copyabilityStatus,
      signalType: signalType(strength, copyabilityStatus),
    };
  });
}

export function consensusForMarket(market: AstroddsMarketScan, consensus: WhaleConsensusSignal[]) {
  return consensus.find((signal) => {
    const sameMarket =
      Boolean(market.marketId && signal.marketId && market.marketId === signal.marketId) ||
      Boolean(market.conditionId && signal.conditionId && market.conditionId === signal.conditionId) ||
      normalizeText(signal.marketTitle).includes(normalizeText(market.marketTitle)) ||
      normalizeText(market.marketTitle).includes(normalizeText(signal.marketTitle));
    const sameSide = normalizeText(signal.side).includes(normalizeText(market.pick)) || normalizeText(market.pick).includes(normalizeText(signal.side));
    return sameMarket && sameSide;
  });
}
