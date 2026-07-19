# Finals MVP

Interactive standings + logistic model for who *should* have won NBA Finals MVP. Built by Noah Ford (MSCS, Carnegie Mellon ’26) as a sports-analytics portfolio project: scrape → feature design → out-of-fold classification → a UI meant for non-technical stakeholders.

## What it does

- **Standings** — Browse Finals years (1984–2026) by season or champion. Each row shows model MVP share, predicted vs actual award, and whether the pick matched. Expand a row for the full share stack and series box stats.
- **Predicted vs Actual** — Toggle the standings strip to compare the model’s top pick against the real Finals MVP.
- **How It Works** — Short project brief: lean feature weights, correlation/VIF diagnostics, and how to read the page.

The model scores each champion Finals top-8 scorer, then softmaxes logits within the year into an **MVP share**. Treat it as a transparent counterfactual on the award, not a guarantee.

## Model (brief)

- **Task:** Binary classification — among champion Finals top scorers, does this player’s series resemble Finals MVP seasons?
- **Algorithm:** Logistic regression on **16** lean series features (e.g. USG%, PTS, NetRtg, shooting rates, minutes, games missed, scoring volatility), with SMOTE inside each training fold for class imbalance.
- **Evaluation:** 5-fold out-of-fold probabilities; year-level pick = argmax of softmaxed OOF logits. Matches the actual award in **38/43** years (1984–2026).
- **Data:** Finals box scores and award history from [Basketball-Reference](https://www.basketball-reference.com/); scraping is intentionally separated from the analysis notebook.
- **Serving:** Precomputed OOF scores → JSON for the Astro UI (no live predict API).

## Stack

| Layer | Choice |
| --- | --- |
| Analysis | Python, pandas, scikit-learn, imbalanced-learn, Jupyter |
| Pipeline | Scrapers + feature builders under `scripts/` |
| Frontend | Astro + React + TypeScript, Tailwind CSS |
| Data | Committed series CSVs → generated `web/src/data/finals.json` |

## Local development

```bash
# Explore / model (uses committed CSVs)
jupyter notebook finalsmvp.ipynb

# After a new Finals season, refresh tables then re-run the notebook
python3 scripts/refresh_data.py

# Frontend — rebuild JSON then run the site
python3 scripts/build_frontend_data.py
cd web && npm install && npm run dev
```

## Project layout

```
finalsmvp.ipynb           # explanatory ML walkthrough (starts from CSVs)
helpers/                  # box scores, meta lookups, softmax, naming
scripts/                  # scrape → features → ML output → frontend JSON
web/                      # Astro + React standings UI
  src/features/standings/
  src/features/how-it-works/
  src/data/finals.json    # generated year summary + candidates
data/
  series_tables/          # committed box-score CSVs (basic/advanced × winner/loser)
  meta/                   # finals_mvp, series games, champions, team IDs
output/                   # model / feature CSVs (+ frontend_finals.json)
```

HTML scrape caches (`data/series_html/`, `data/teams/html/`) are optional and gitignored; the notebook and UI read the CSV layer.

## Notes for recruiters

- End-to-end path: scrape Basketball-Reference → engineer lean series features → OOF logistic with imbalance handling → ship an interactive UI that compares model picks to the actual award.
- Emphasis on **communicating the award counterfactual** (MVP share, predicted vs actual, expandable box scores, feature-weight transparency) as much as on raw hit rate.
- Honest limits: box scores miss narrative and defensive reputation; the model is strongest when one star clearly leads scoring/usage, and can miss years with two near-equal candidates.

## Possible next work

- Richer clutch / series-context features beyond the lean set
- Stronger evaluation reporting (calibration, era holdouts)
- Live predict API for counterfactual “what if this player’s series looked like X?”

## License

Personal portfolio project — see repository for terms.
