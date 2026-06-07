import { calculateOrderBookMetrics, fetchOrderBooks } from "../sports-data/orderbook";
import { compactId, normalizeText } from "../sports-data/normalize";
import type { AstroddsOrderBook } from "../sports-data/types";
import { categoryAllowed, classifyPolymarketMarket, type WhaleMarketCategory } from "./market-classifier";
import { calculatePositionCopyability } from "./whale-strategy";
import type { CopyabilityStatus, WalletPosition, WhaleOnlySignal } from "./types";

export type WhaleSignalBuildOptions = {
  category?: string;
  telegramConfigured?: boolean;
  telegramAlertsEnabled?: boolean;
};

function entryBucket(value?: number) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "unknown";
}

function signalKey(position: WalletPosition) {
  const day = new Date().toISOString().slice(0, 10);
  return [
    normalizeText(position.handle),
    position.marketId ?? position.conditionId ?? compactId(position.marketTitle),
    normalizeText(position.side || position.outcome),
    entryBucket(position.avgEntryPrice),
    day,
  ].join("|");
}

function currentPrice(position: WalletPosition, bestAsk?: number) {
  if (typeof position.currentPrice === "number") return position.currentPrice;
  if (typeof bestAsk === "number") return bestAsk;
  return undefined;
}

function telegramStatus(input: {
  copyability: WhaleOnlySignal["copyability"];
  configured?: boolean;
  enabled?: boolean;
  hasPrice: boolean;
  active: boolean;
}) {
  if (!input.active) return { status: "NOT_QUALIFIED" as const, reason: "Market/position is not open." };
  if (!input.hasPrice) return { status: "NOT_QUALIFIED" as const, reason: "No current public price available." };
  if (input.copyability !== "COPYABLE_NOW" && input.copyability !== "NEAR_WHALE_ENTRY") {
    return { status: "NOT_QUALIFIED" as const, reason: "Trade is stale, too late, illiquid, or watch-only." };
  }
  if (!input.configured) return { status: "NOT_CONFIGURED" as const, reason: "Telegram token/chat is not configured." };
  if (!input.enabled) return { status: "DISABLED" as const, reason: "Telegram whale alerts are disabled." };
  return { status: "READY" as const, reason: "Copyable public whale trade is ready for Telegram alert workflow." };
}

export async function buildWhaleOnlySignals(
  positions: WalletPosition[],
  options: WhaleSignalBuildOptions = {},
): Promise<{ signals: WhaleOnlySignal[]; errors: string[] }> {
  const errors: string[] = [];
  const allowedCategory = options.category ?? "all";
  const open = positions.filter((position) => position.status === "OPEN");
  const tokenIds = Array.from(new Set(open.map((position) => position.assetId).filter((id): id is string => Boolean(id))));
  let books = new Map<string, AstroddsOrderBook>();

  if (tokenIds.length) {
    try {
      books = await fetchOrderBooks(tokenIds);
    } catch (error) {
      errors.push(error instanceof Error ? error.message : "Unknown order book fetch failure.");
    }
  }

  const signals = open.flatMap((position) => {
    const classified = classifyPolymarketMarket(position.marketTitle, position.category);
    const category = position.category ?? classified.category;
    if (!categoryAllowed(category, allowedCategory)) return [];

    const book = position.assetId ? books.get(position.assetId) : undefined;
    const orderBook = calculateOrderBookMetrics(book);
    const copyability = calculatePositionCopyability(position, book ? orderBook : undefined);
    const price = currentPrice(position, orderBook.bestAsk);
    const telegram = telegramStatus({
      copyability: copyability.status,
      configured: options.telegramConfigured,
      enabled: options.telegramAlertsEnabled,
      hasPrice: typeof price === "number",
      active: position.status === "OPEN",
    });
    const whaleEntry = position.avgEntryPrice;

    return [{
      signalKey: signalKey(position),
      signalType: "WHALE_ONLY_PUBLIC_SIGNAL" as const,
      whale: position.handle,
      address: position.address,
      category: category as WhaleMarketCategory,
      sport: position.sportCategory ?? classified.sport,
      marketId: position.marketId,
      conditionId: position.conditionId,
      assetId: position.assetId,
      market: position.marketTitle,
      marketType: classified.marketType,
      side: position.side,
      outcome: position.outcome,
      whaleEntryPrice: whaleEntry,
      currentPrice: price,
      priceDelta: typeof whaleEntry === "number" && typeof price === "number" ? price - whaleEntry : undefined,
      positionValue: position.positionValue,
      shares: position.shares,
      status: position.status,
      copyability: copyability.status,
      copyabilityReason: copyability.reason,
      orderBookStatus: book ? orderBook.status : "UNKNOWN",
      orderBook: book ? orderBook : undefined,
      createdAt: position.createdAt,
      updatedAt: position.updatedAt,
      telegramStatus: telegram.status,
      telegramReason: telegram.reason,
    }];
  });

  return {
    signals: signals.sort((a, b) => {
      const rank: Record<CopyabilityStatus, number> = {
        COPYABLE_NOW: 5,
        NEAR_WHALE_ENTRY: 4,
        WATCH_ONLY: 3,
        UNKNOWN: 2,
        STALE_ENTRY: 1,
        TOO_LATE: 0,
        NO_LIQUIDITY: 0,
        CONFLICT: 0,
      };
      return (rank[b.copyability] ?? 0) - (rank[a.copyability] ?? 0) || (b.positionValue ?? 0) - (a.positionValue ?? 0);
    }),
    errors,
  };
}
