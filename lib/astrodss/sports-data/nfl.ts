import type { AstroddsGameScan } from "./types";
import { scanSportsDbLeague } from "./sportsdb";

export function scanNFLGames(signal?: AbortSignal): Promise<AstroddsGameScan[]> {
  return scanSportsDbLeague(
    {
      sport: "NFL",
      league: "NFL",
      leagueId: "4391",
      weatherRelevant: true,
      keyPlayerLabel: "QB status",
      sourceNote: "PARTIAL - free schedule only; QB status, injuries, matchup ratings, and line movement need a provider.",
    },
    signal,
  );
}
