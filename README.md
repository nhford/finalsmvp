## Who should've won NBA Finals MVP?

### A Python Machine Learning Analysis

The **notebook is analysis-only**. Scraping Basketball-Reference is intentionally separate — HTML quirks and rate limits don't belong in the story.

### Quick start

```bash
# Explore / model (uses committed CSVs)
jupyter notebook finalsmvp.ipynb

# After a new Finals season, refresh tables then re-run the notebook
python3 scripts/refresh_data.py

# Frontend (Astro + React) — rebuild JSON then run the site
python3 scripts/build_frontend_data.py
cd web && npm install && npm run dev
```

### Layout

```text
finalsmvp.ipynb                 # explanatory ML walkthrough (starts from CSVs)
helpers/                        # analysis helpers (box scores, meta lookups, softmax)
scripts/
  refresh_data.py               # scrape → parse team meta → build top-8 features
  update_finals_through_2026.py # Basketball-Reference scrape (HTML cache → CSVs)
  parse_team_meta.py            # team #meta HTML → champions_seasons.csv
  build_top8.py                 # series_tables → output/full_top_8*.csv + finals_series_games.csv
  build_ml_output.py            # lean OOF logistic → machine_learning_output.csv
  extract_advanced_winners.py   # series HTML → advanced/winner CSVs
  build_frontend_data.py        # ML + advanced + logos → web JSON

web/                            # Astro + React standings UI (Hot Seat–style)
  src/data/finals.json          # generated year summary + candidates

data/
  series_tables/                # committed box-score CSVs (basic/advanced × winner/loser)
  meta/                         # finals_mvp, finals_series_games, champions, team IDs
  teams/
    champions_seasons.csv       # committed season summary + logo URLs
    champions_playoff_rounds.csv
    html/                       # gitignored: {ABBREV}_{year}.html
  series_html/                  # gitignored scrape cache
    finals/                     # {year}_nba_finals_{a}_vs_{b}.html
    meta/                       # finals_mvp.html, playoffs_series.html

output/                         # model / feature outputs (+ frontend_finals.json)
tableau/                        # Tableau workbook + screenshots
```

### HTML naming

| Kind | Pattern | Example |
|------|---------|---------|
| Finals series page | `{year}_nba_finals_{a}_vs_{b}.html` | `finals/2024_nba_finals_mavericks_vs_celtics.html` |
| Box-score CSV stem | same as series HTML (no extension) | `2024_nba_finals_mavericks_vs_celtics.csv` |
| Team season meta | `{ABBREV}_{year}.html` | `BOS_2024.html` |
| Award / index pages | `series_html/meta/{name}.html` | `meta/finals_mvp.html` |

Helpers live in [`helpers/naming.py`](helpers/naming.py).

### What matters

- [`finalsmvp.ipynb`](finalsmvp.ipynb) — data peek → features → baselines → logistic regression → mistakes/viz
- [`output/`](output) — CSVs written at key notebook steps
- [`tableau/`](tableau) — visualizations

<img src="/tableau/predictions_crop.png" alt="Predictions Cropped" style="width:100%;height:100%; padding-top:10px">

### HTML caches

`data/series_html/` and `data/teams/html/` are **optional local caches** written by the scrape scripts. They are gitignored. The notebook and Tableau logo column use the CSV layer (`series_tables`, `champions_seasons.csv`).

### Development

Python + pandas + scikit-learn + imbalanced-learn.
