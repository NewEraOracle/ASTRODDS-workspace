import type {
  AstroddsEntryQuality,
  AstroddsMarketScan,
  AstroddsOrderBook,
  AstroddsOrderBookLevel,
  AstroddsOrderBookMetrics,
  AstroddsScanDiagnostics,
  AstroddsSourceMode,
} from "./types";
import { safeNumber } from "./normalize";

export const POLYMARKET_CLOB_BOOK_URL = "https://clob.polymarket.com/book";
export const POLYMARKET_CLOB_BOOKS_URL = "https://clob.polymarket.com/books";
export const DEFAULT_PAPER_TRADE_SIZE = 50;

type RawOrderBookLevel = {
  price?: string | number;
  size?: string | number;
};

type RawOrderBook = {
  asset_id?: string;
  token_id?: string;
  market?: string;
  bids?: RawOrderBookLevel[];
  asks?: RawOrderBookLevel[];
  last_trade_price?: string | number;
  lastTradePrice?: string | number;
};

function normalizeLevels(levels: RawOrderBookLevel[] | undefined, side: "bid" | "ask") {
  const normalized = (levels ?? [])
    .map((level) => ({
      price: safeNumber(level.price) ?? 0,
      size: safeNumber(level.size) ?? 0,
    }))
    .filter((level) => level.price > 0 && level.size > 0);

  return normalized.sort((a, b) => (side === "ask" ? a.price - b.price : b.price - a.price));
}

function levelDollarDepth(levels: AstroddsOrderBookLevel[]) {
  return levels.reduce((total, level) => total + level.price * level.size, 0);
}

function levelsWithin(levels: AstroddsOrderBookLevel[], referencePrice: number | undefined, percent: number) {
  if (!referencePrice) return [];
  const maxPrice = referencePrice * (1 + percent);
  return levels.filter((level) => level.price <= maxPrice);
}

function estimateAskFill(asks: AstroddsOrderBookLevel[], targetStake: number) {
  let remaining = targetStake;
  let spent = 0;
  let shares = 0;

  for (const ask of asks) {
    if (remaining <= 0) break;
    const levelCost = ask.price * ask.size;
    const spend = Math.min(remaining, levelCost);
    spent += spend;
    shares += spend / ask.price;
    remaining -= spend;
  }

  return {
    spent,
    shares,
    remaining: Math.max(0, remaining),
    averagePrice: shares > 0 ? spent / shares : undefined,
  };
}

function scoreEntryQuality(input: {
  bestAsk?: number;
  spread?: number;
  spreadPercent?: number;
  fillStatus: AstroddsOrderBookMetrics["fillStatus"];
  estimatedSlippage?: number;
  depthWithin1Percent: number;
  depthWithin3Percent: number;
}) {
  if (!input.bestAsk || input.fillStatus === "NOT_ENOUGH_LIQUIDITY") {
    return { quality: "NO_LIQUIDITY" as AstroddsEntryQuality, score: 0 };
  }

  let score = 8;
  if ((input.spread ?? 1) <= 0.015) score += 7;
  else if ((input.spread ?? 1) <= 0.03) score += 5;
  else if ((input.spread ?? 1) <= 0.06) score += 2;
  else score -= 4;

  if ((input.spreadPercent ?? 1) <= 0.04) score += 4;
  else if ((input.spreadPercent ?? 1) >= 0.12) score -= 4;

  if (input.depthWithin1Percent >= DEFAULT_PAPER_TRADE_SIZE) score += 4;
  else if (input.depthWithin3Percent >= DEFAULT_PAPER_TRADE_SIZE) score += 2;
  else score -= 3;

  if ((input.estimatedSlippage ?? 1) <= 0.01) score += 2;
  else if ((input.estimatedSlippage ?? 1) >= 0.05) score -= 4;

  if (input.fillStatus === "PARTIAL") score -= 6;

  if (score >= 20) return { quality: "EXCELLENT" as AstroddsEntryQuality, score: 25 };
  if (score >= 16) return { quality: "GOOD" as AstroddsEntryQuality, score: 20 };
  if (score >= 11) return { quality: "FAIR" as AstroddsEntryQuality, score: 14 };
  return { quality: "POOR" as AstroddsEntryQuality, score: 6 };
}

function statusFromQuality(quality: AstroddsEntryQuality): AstroddsOrderBookMetrics["status"] {
  if (quality === "EXCELLENT") return "EXCELLENT";
  if (quality === "GOOD") return "GOOD";
  if (quality === "FAIR") return "FAIR";
  if (quality === "NO_LIQUIDITY") return "NO_LIQUIDITY";
  if (quality === "UNKNOWN") return "NOT_CONNECTED";
  return "POOR";
}

export async function fetchOrderBook(tokenId: string, signal?: AbortSignal): Promise<AstroddsOrderBook> {
  const url = new URL(POLYMARKET_CLOB_BOOK_URL);
  url.searchParams.set("token_id", tokenId);

  const response = await fetch(url, {
    signal,
    next: { revalidate: 20 },
    headers: { accept: "application/json" },
  });

  if (!response.ok) {
    throw new Error(`Polymarket CLOB book returned ${response.status}`);
  }

  return normalizeOrderBook((await response.json()) as RawOrderBook, tokenId);
}

export async function fetchOrderBooks(tokenIds: string[], signal?: AbortSignal): Promise<Map<string, AstroddsOrderBook>> {
  const uniqueTokenIds = Array.from(new Set(tokenIds.filter(Boolean)));
  const books = new Map<string, AstroddsOrderBook>();
  if (!uniqueTokenIds.length) return books;

  const settled = await Promise.allSettled(uniqueTokenIds.map((tokenId) => fetchOrderBook(tokenId, signal)));
  settled.forEach((result) => {
    if (result.status === "fulfilled") books.set(result.value.tokenId, result.value);
  });

  return books;
}

export function normalizeOrderBook(rawBook: RawOrderBook, fallbackTokenId?: string): AstroddsOrderBook {
  const tokenId = String(rawBook.asset_id ?? rawBook.token_id ?? fallbackTokenId ?? "");

  return {
    tokenId,
    bids: normalizeLevels(rawBook.bids, "bid"),
    asks: normalizeLevels(rawBook.asks, "ask"),
    lastTradePrice: safeNumber(rawBook.last_trade_price ?? rawBook.lastTradePrice),
    sourceUrl: tokenId ? `${POLYMARKET_CLOB_BOOK_URL}?token_id=${encodeURIComponent(tokenId)}` : POLYMARKET_CLOB_BOOK_URL,
  };
}

export function calculateOrderBookMetrics(
  book: AstroddsOrderBook | undefined,
  targetStake = DEFAULT_PAPER_TRADE_SIZE,
  sourceMode?: AstroddsSourceMode,
): AstroddsOrderBookMetrics {
  if (!book) {
    return {
      status: "NOT_CONNECTED",
      sourceMode,
      depthAtBestAsk: 0,
      depthAtBestBid: 0,
      depthWithin1Percent: 0,
      depthWithin3Percent: 0,
      estimatedShares: 0,
      fillStatus: "UNKNOWN",
      remainingUnfilledAmount: targetStake,
      liquidityScore: 0,
      orderBookScore: 0,
      entryQuality: "UNKNOWN",
      summary: "Order Book: NOT CONNECTED - CLOB depth unavailable.",
    };
  }

  const bestAsk = book.asks[0]?.price;
  const bestBid = book.bids[0]?.price;
  const midpoint = bestBid && bestAsk ? (bestBid + bestAsk) / 2 : undefined;
  const spread = bestBid && bestAsk ? bestAsk - bestBid : undefined;
  const spreadPercent = midpoint && spread !== undefined ? spread / midpoint : undefined;
  const depthAtBestAsk = book.asks[0] ? book.asks[0].price * book.asks[0].size : 0;
  const depthAtBestBid = book.bids[0] ? book.bids[0].price * book.bids[0].size : 0;
  const depthWithin1Percent = levelDollarDepth(levelsWithin(book.asks, bestAsk, 0.01));
  const depthWithin3Percent = levelDollarDepth(levelsWithin(book.asks, bestAsk, 0.03));
  const fill = estimateAskFill(book.asks, targetStake);
  const fillStatus = fill.remaining <= 0.01 ? "OK" : fill.spent > 0 ? "PARTIAL" : "NOT_ENOUGH_LIQUIDITY";
  const estimatedSlippage = bestAsk && fill.averagePrice ? Math.max(0, fill.averagePrice - bestAsk) : undefined;
  const { quality, score } = scoreEntryQuality({
    bestAsk,
    spread,
    spreadPercent,
    fillStatus,
    estimatedSlippage,
    depthWithin1Percent,
    depthWithin3Percent,
  });
  const spreadText = typeof spread === "number" ? spread.toFixed(3) : "--";
  const askText = typeof bestAsk === "number" ? bestAsk.toFixed(2) : "--";
  const fillText = fillStatus === "OK" ? "$50 fill OK" : fillStatus === "PARTIAL" ? "$50 fill partial" : "Not enough liquidity";

  return {
    status: statusFromQuality(quality),
    sourceMode,
    bestBid,
    bestAsk,
    midpoint,
    spread,
    spreadPercent,
    lastTradePrice: book.lastTradePrice,
    depthAtBestAsk,
    depthAtBestBid,
    depthWithin1Percent,
    depthWithin3Percent,
    estimatedShares: fill.shares,
    estimatedAverageFillPrice: fill.averagePrice,
    estimatedSlippage,
    fillStatus,
    remainingUnfilledAmount: fill.remaining,
    liquidityScore: Math.min(25, Math.round((depthWithin3Percent / targetStake) * 10)),
    orderBookScore: score,
    entryQuality: quality,
    summary: `Order Book: ${statusFromQuality(quality).replace(/_/g, " ")} - Best Ask ${askText}, Spread ${spreadText}, ${fillText}.`,
    sourceUrl: book.sourceUrl,
  };
}

export function scoreOrderBook(metrics?: AstroddsOrderBookMetrics) {
  return metrics?.orderBookScore ?? 0;
}

export async function hydrateMarketsWithOrderBooks(
  markets: AstroddsMarketScan[],
  signal?: AbortSignal,
  sourceMode: AstroddsSourceMode = "SERVER",
): Promise<{ markets: AstroddsMarketScan[]; diagnostics: AstroddsScanDiagnostics["orderBook"] }> {
  const tokenIds = Array.from(new Set(markets.map((market) => market.assetId).filter(Boolean) as string[]));
  if (!tokenIds.length) {
    return {
      markets,
      diagnostics: {
        status: "NOT_CONNECTED",
        sourceMode,
        orderBooksRequested: 0,
        orderBooksFetched: 0,
        orderBooksFailed: 0,
        sourceUrl: POLYMARKET_CLOB_BOOK_URL,
      },
    };
  }

  const settled = await Promise.allSettled(tokenIds.map((tokenId) => fetchOrderBook(tokenId, signal)));
  const books = new Map<string, AstroddsOrderBook>();
  const failedTokenIds: string[] = [];
  const errors: string[] = [];

  settled.forEach((result, index) => {
    const tokenId = tokenIds[index];
    if (result.status === "fulfilled") {
      books.set(result.value.tokenId, result.value);
    } else {
      failedTokenIds.push(tokenId);
      errors.push(result.reason instanceof Error ? result.reason.message : "Unknown order book fetch failure");
    }
  });

  const hydrated = markets.map((market) => ({
    ...market,
    orderBook: calculateOrderBookMetrics(market.assetId ? books.get(market.assetId) : undefined, DEFAULT_PAPER_TRADE_SIZE, sourceMode),
  }));
  const fetched = books.size;
  const status = fetched === tokenIds.length ? "CONNECTED_SERVER" : fetched > 0 ? "PARTIAL" : "FAILED";

  return {
    markets: hydrated,
    diagnostics: {
      status: sourceMode === "BROWSER_FALLBACK" && fetched === tokenIds.length ? "CONNECTED_BROWSER" : status,
      sourceMode: fetched > 0 ? sourceMode : "FAILED",
      orderBooksRequested: tokenIds.length,
      orderBooksFetched: fetched,
      orderBooksFailed: tokenIds.length - fetched,
      sourceUrl: POLYMARKET_CLOB_BOOK_URL,
      failedTokenIds: failedTokenIds.slice(0, 20),
      error: errors.length ? Array.from(new Set(errors)).slice(0, 3).join(" | ") : undefined,
    },
  };
}
