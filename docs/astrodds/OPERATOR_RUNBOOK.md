# ASTRODDS Operator Runbook

Generated UTC: 2026-06-14T15:36:57.386327Z

## Status

ASTRODDS is launch-ready with documented limits.

## Daily operation

- Do not run the full runner manually unless needed.
- Credit guard protects the odds credits.
- Default daily scan limit: 3 scans/day.
- Scheduled tasks run morning, afternoon, and evening.
- Public Telegram sends only official actionable buys.
- Review board is admin/internal only.

## Main commands

Health check:

```powershell
powershell -ExecutionPolicy Bypass -File ".\mlb-engine\baseballpred-inspired\scripts\45_astrodds_health_check.ps1"
```

Credit status:

```powershell
python ".\mlb-engine\baseballpred-inspired\scripts\48_credit_guard.py" status
```

Public proof log:

```text
public/astrodds-proof-log.html
public/astrodds-proof-log.json
```

## Rules

- Paper/manual only.
- No real-money automation.
- No guaranteed profit.
- Public client alerts only show official buys.
- Do not chase above Entry max.
- Recommended stake is 5% bankroll.
