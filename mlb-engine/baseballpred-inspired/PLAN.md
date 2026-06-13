ASTRODDS BaseballPred-Inspired Upgrade

Goal:
Build a real MLB prediction engine, not just a nice dashboard.

Reference:
https://github.com/numeristical/resources/tree/master/BaseballPred

Modules to build:

1. odds\_features
* sportsbook moneyline
* implied probability
* opening price if available
* current price
* closing price later
* line movement
* CLV later
2. starting\_pitcher\_features
* pitcher handedness
* ERA
* WHIP if available
* strikeouts
* walks if available
* recent form
* home/away adjustment
* pitcher missing flag
3. bullpen\_features
* bullpen recent innings
* reliever fatigue
* bullpen ERA if available
* back-to-back usage if available
* missing bullpen flag
4. batting\_lineup\_features
* team season offense
* recent offense
* confirmed lineup if available
* missing lineup penalty
* handedness matchup later
5. weather\_park\_features
* temperature
* wind
* precipitation
* park factor
* dome/open air if available
6. model\_training
* train on historical completed games only
* output calibrated win probability
* validate by season split
* never train on future games
7. edge\_evaluation
* model probability vs sportsbook implied probability
* edge
* ROI by edge bucket
* win rate by confidence bucket
* Brier score
* log loss
* CLV later
8. production\_filter
Only show max 10 picks:
* moneyline only
* selectedSide is real team
* marketProbability 0.30 to 0.75
* edge positive
* edge not absurd
* confidence high/medium
* risk not high
* no duplicate game
* paper/manual until backtest proves ROI

Do not touch UI until model report improves.

