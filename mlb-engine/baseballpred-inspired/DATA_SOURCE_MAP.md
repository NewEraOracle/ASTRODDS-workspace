ASTRODDS MLB PREDICTION ENGINE — DATA SOURCE MAP

Goal:
Build a real MLB moneyline prediction engine from 2016-current, inspired by BaseballPred.

Reference:
https://github.com/numeristical/resources/tree/master/BaseballPred

BASEBALLPRED STRUCTURE TO MIRROR:
1. Data wrangle
2. First model
3. Odds data
4. Odds analysis
5. Raw pitching data
6. Pitching features
7. Starting pitcher model
8. Bullpen data
9. Bullpen model
10. Batter / lineup data
11. Lineup model
12. Edge evaluation

FREE / LOW COST DATA SOURCES:

1. MLB StatsAPI
Use for:
- schedule
- game IDs
- home/away teams
- scores
- game status
- probable pitchers
- boxscores
- lineups when available

2. pybaseball
Use for:
- Statcast data
- batting stats
- pitching stats
- FanGraphs-style leaderboards if available
- historical features 2016-current

3. Retrosheet
Use for:
- historical game logs
- play-by-play
- backtesting
- team/player logs

4. Open-Meteo
Use for:
- weather forecast
- historical weather
- temperature
- wind
- precipitation
- humidity
- park/weather context

5. The Odds API
Use for:
- current sportsbook moneyline odds
- implied probability
- line movement if saved over time
- CLV later

RULES:
- Never fake probability.
- Never use future data in training.
- Always split train/test by season.
- Always compare model probability vs sportsbook market probability.
- Only bet when edge survives backtest.
- Do not force 10 picks.
- Quality > quantity.
