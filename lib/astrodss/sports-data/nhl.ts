import type { AstroddsGameScan } from "./types";
import { scanSportsDbLeague } from "./sportsdb";

export function scanNHLGames(signal?: AbortSignal): Promise<AstroddsGameScan[]> {
  return scanSportsDbLeague(
    {
      sport: "NHL",
      league: "NHL",
      leagueId: "4380",
      weatherRelevant: false,
      keyPlayerLabel: "Starting goalie",
      sourceNote: "PARTIAL - free schedule only; starting goalies, injuries, rest, power play, and penalty kill need a provider.",
    },
    signal,
  );
}
