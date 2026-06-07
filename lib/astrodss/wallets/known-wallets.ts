import type { KnownWhaleWallet } from "./types";

export const KNOWN_WHALE_WALLETS: KnownWhaleWallet[] = [
  {
    handle: "kch123",
    profileUrl: "https://polymarket.com/@kch123",
    rank: "WHALE_WATCH",
    source: "manual_polymarket_research",
    notes: "High-profit Polymarket trader. Analyze sport-specific record, entry price discipline, and copyability before using as signal.",
  },
  {
    handle: "afghj2421",
    profileUrl: "https://polymarket.com/@afghj2421",
    rank: "WHALE_WATCH",
    source: "manual_polymarket_research",
    notes: "Profitable Polymarket trader found manually. Verify wallet/activity from public data.",
  },
  {
    handle: "RN1",
    profileUrl: "https://polymarket.com/@rn1",
    rank: "WHALE_WATCH",
    source: "manual_polymarket_research",
    notes: "High-volume Polymarket profile. Verify public wallet/activity and sport-specific performance.",
  },
  {
    handle: "swisstony",
    profileUrl: "https://polymarket.com/@swisstony",
    rank: "WHALE_WATCH",
    source: "manual_polymarket_research",
    notes: "Very high PnL profile from manual research. Verify using public Polymarket data before signal use.",
  },
];

export function nextWhaleRescanAt(rank: KnownWhaleWallet["rank"], hasActiveSportsPositions = false) {
  const date = new Date();
  const hours =
    rank === "ELITE_TRADER"
      ? hasActiveSportsPositions
        ? 0.25
        : 0.5
      : rank === "DIAMOND_CANDIDATE"
        ? hasActiveSportsPositions
          ? 0.5
          : 1
        : rank === "WHALE_WATCH"
          ? hasActiveSportsPositions
            ? 1
            : 6
          : 24 * 7;

  date.setMinutes(date.getMinutes() + Math.round(hours * 60));
  return date.toISOString();
}
