import type { AstroddsGameScan } from "./types";
import { scanSportsDbLeague } from "./sportsdb";

export function scanNBAGames(signal?: AbortSignal): Promise<AstroddsGameScan[]> {
  return scanSportsDbLeague(
    {
      sport: "NBA",
      league: "NBA",
      leagueId: "4387",
      weatherRelevant: false,
      keyPlayerLabel: "Star player status",
      sourceNote: "PARTIAL - free schedule only; injuries, starting lineups, rest, pace, offensive rating, and defensive rating need a provider.",
    },
    signal,
  );
}
