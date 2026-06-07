import { inferBetType, normalizeText } from "../sports-data/normalize";
import type { WalletMarketType } from "./types";

export type WhaleMarketCategory =
  | "SPORTS"
  | "POLITICS"
  | "ELECTION"
  | "CRYPTO"
  | "FINANCE"
  | "WEATHER"
  | "CULTURE"
  | "MACRO"
  | "OTHER"
  | "UNKNOWN";

export type WhaleSportCategory = "MLB" | "NHL" | "NBA" | "NFL" | "SOCCER" | "TENNIS" | "MMA" | "OTHER_SPORT";

export type ClassifiedMarket = {
  category: WhaleMarketCategory;
  sport?: WhaleSportCategory;
  marketType: WalletMarketType | "OUTRIGHT";
};

const sportKeywords: Record<WhaleSportCategory, string[]> = {
  MLB: ["mlb", "baseball", "dodgers", "yankees", "mets", "red sox", "cubs", "phillies", "braves", "blue jays"],
  NHL: ["nhl", "hockey", "stanley cup", "oilers", "panthers", "maple leafs", "red wings", "rangers"],
  NBA: ["nba", "basketball", "finals", "lakers", "celtics", "raptors", "clippers", "knicks"],
  NFL: ["nfl", "football", "super bowl", "chiefs", "eagles", "cowboys", "packers"],
  SOCCER: ["soccer", "premier league", "champions league", "world cup", "epl", "mls"],
  TENNIS: ["tennis", "wimbledon", "atp", "wta", "us open", "french open"],
  MMA: ["mma", "ufc", "fight night", "bout"],
  OTHER_SPORT: ["sports", "olympics", "golf", "f1", "formula 1", "nascar"],
};

function sportFromText(text: string): WhaleSportCategory | undefined {
  const normalized = normalizeText(text);
  return (Object.keys(sportKeywords) as WhaleSportCategory[]).find((sport) =>
    sportKeywords[sport].some((keyword) => normalized.includes(keyword)),
  );
}

function categoryFromText(text: string): WhaleMarketCategory {
  const normalized = normalizeText(text);
  if (sportFromText(normalized)) return "SPORTS";
  if (/\belection\b|\bpresident\b|\bsenate\b|\bcongress\b|\bprimary\b|\bnominee\b|\bvote\b/.test(normalized)) return "ELECTION";
  if (/\bpolitics\b|\btrump\b|\bbiden\b|\bgovernment\b|\bcabinet\b|\bmayor\b|\bgovernor\b/.test(normalized)) return "POLITICS";
  if (/\bcrypto\b|\bbitcoin\b|\beth\b|\bethereum\b|\bsolana\b|\bxrp\b|\bdogecoin\b|\bbtc\b/.test(normalized)) return "CRYPTO";
  if (/\bstock\b|\bipo\b|\brate cut\b|\bfed\b|\bearnings\b|\bnasdaq\b|\bs&p\b|\btariff\b|\btreasury\b/.test(normalized)) return "FINANCE";
  if (/\bweather\b|\brain\b|\bsnow\b|\bhurricane\b|\btemperature\b|\bstorm\b|\bheat\b/.test(normalized)) return "WEATHER";
  if (/\boscar\b|\bgrammy\b|\bmovie\b|\btv\b|\bculture\b|\bsong\b|\bstreaming\b|\bcelebrity\b/.test(normalized)) return "CULTURE";
  if (/\binflation\b|\bcpi\b|\bgdp\b|\bunemployment\b|\brecession\b|\bmacro\b|\boil\b/.test(normalized)) return "MACRO";
  return normalized ? "OTHER" : "UNKNOWN";
}

function marketTypeFromText(text: string): WalletMarketType | "OUTRIGHT" {
  const normalized = normalizeText(text);
  if (/\bchampion\b|\bwinner\b|\boutright\b|\bwho will win\b|\bworld series\b|\bstanley cup\b|\bsuper bowl\b/.test(normalized)) return "OUTRIGHT";
  if (/\bfuture\b|\bseason\b|\bmake playoffs\b|\bdivision\b|\bmvp\b|\bcy young\b/.test(normalized)) return "FUTURE";
  const inferred = inferBetType(text);
  if (inferred === "YES_NO") return "YES_NO";
  return inferred;
}

export function classifyPolymarketMarket(title?: string, metadata?: string): ClassifiedMarket {
  const text = [title, metadata].filter(Boolean).join(" ");
  const category = categoryFromText(text);

  return {
    category,
    sport: category === "SPORTS" ? sportFromText(text) ?? "OTHER_SPORT" : undefined,
    marketType: marketTypeFromText(text),
  };
}

export function categoryAllowed(category: WhaleMarketCategory, allowed: string | undefined) {
  const normalized = normalizeText(allowed ?? "all");
  if (!normalized || normalized === "all") return true;
  return normalized.split(/[\s,]+/).some((item) => normalizeText(item) === normalizeText(category));
}
