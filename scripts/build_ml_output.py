"""Fit OOF lean logistic model → output/machine_learning_output.csv."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from helpers.boxscores import (
    LEAN_MODEL_FEATURE_COLS,
    normalize_player_name,
    select_model_features,
)
from helpers.features import softmax_shares
from helpers.meta import champ_from_year, mvp_from_year
from helpers.paths import (
    FEATURE_WEIGHTS_JSON,
    FULL_TOP_8_UNRANKED_ADVANCED_CSV,
    OUTPUT_DIR,
)


def fit_oof_logistic(players: pd.DataFrame):
    """5-fold OOF logistic on columns present (Year/Player/mvp excluded)."""
    X = players.drop(columns=["Year", "Player", "mvp"])
    y = players["mvp"].astype(int)

    clf = LogisticRegression(max_iter=1000)
    smote = SMOTE(sampling_strategy="minority", random_state=42)
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    scaler = StandardScaler()

    oof_prob = np.zeros(len(X))
    oof_logits = np.zeros(len(X))

    for train_index, test_index in kf.split(X):
        X_tr, X_te = X.iloc[train_index], X.iloc[test_index]
        y_tr = y.iloc[train_index]

        X_tr_s = scaler.fit_transform(X_tr)
        X_te_s = scaler.transform(X_te)
        X_res, y_res = smote.fit_resample(X_tr_s, y_tr)

        clf.fit(X_res, y_res)
        oof_prob[test_index] = clf.predict_proba(X_te_s)[:, 1]
        oof_logits[test_index] = clf.decision_function(X_te_s)

    out = players[["Year", "Player", "mvp"]].reset_index(drop=True).copy()
    out["prob_mvp"] = np.round(oof_prob, 2)
    out["Binary"] = (oof_prob >= 0.5).astype(int)
    out["Correct"] = out["Binary"] == out["mvp"].astype(int)
    out.insert(1, "MVP", out["Year"].apply(mvp_from_year))
    out.insert(1, "Team", out["Year"].apply(champ_from_year))
    out["mvp_share"] = (
        pd.Series(oof_logits)
        .groupby(out["Year"].values)
        .transform(lambda s: softmax_shares(s.to_numpy()))
        .round(3)
        .to_numpy()
    )
    out.insert(
        out.columns.get_loc("mvp_share"),
        "Rank",
        out.groupby(["Year", "Team"])["mvp_share"]
        .rank(ascending=False, method="dense")
        .astype(int),
    )
    front = ["Year", "Team", "MVP", "Player", "mvp_share"]
    rest = [c for c in out.columns if c not in front]
    out = out[front + rest]
    return out, clf, X, y


def summarize_accuracy(out: pd.DataFrame, label: str) -> None:
    picks = out.loc[out.groupby("Year")["mvp_share"].idxmax()]
    year_hits = int(
        (
            picks["Player"].map(normalize_player_name)
            == picks["MVP"].map(normalize_player_name)
        ).sum()
    )
    year_n = len(picks)
    y_true = out["mvp"].astype(int)
    y_pred = out["Binary"]
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    print(f"{label}")
    print(f"  features: {list(LEAN_MODEL_FEATURE_COLS)}")
    print(f"  player binary accuracy: {out['Correct'].mean():.3f}")
    print(f"  MVP recall / precision: {recall:.3f} / {precision:.3f}")
    print(f"  year argmax(mvp_share): {year_hits}/{year_n} ({year_hits / year_n:.3f})")


def main() -> None:
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(FULL_TOP_8_UNRANKED_ADVANCED_CSV)
    raw = raw.loc[:, ~raw.columns.str.match(r"^Unnamed")]
    players = select_model_features(raw, advanced=True)
    out, clf, X, _y = fit_oof_logistic(players)
    out_path = Path(OUTPUT_DIR) / "machine_learning_output.csv"
    out.to_csv(out_path, index=False)

    coefs = pd.Series(clf.coef_[0], index=X.columns).sort_values(ascending=False)
    weights_path = Path(FEATURE_WEIGHTS_JSON)
    weights_payload = {
        "note": "Standardized logistic coefficients from the last OOF fold fit",
        "features": [
            {"name": str(name), "weight": round(float(value), 3)}
            for name, value in coefs.items()
        ],
    }
    weights_path.write_text(
        json.dumps(weights_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {out_path} ({out.Year.nunique()} years, {len(out)} rows)")
    print(f"Wrote {weights_path}")
    summarize_accuracy(out, "LEAN + advanced")
    print("\nStandardized coefs (last OOF fold fit):")
    print(coefs.round(3).to_string())


if __name__ == "__main__":
    main()
