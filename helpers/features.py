"""Feature-engineering helpers for ranking / analytic scores."""

from __future__ import annotations

import numpy as np
import pandas as pd


def softmax_shares(scores: np.ndarray | list[float]) -> np.ndarray:
    """Numerically stable softmax; returns shares that sum to 1."""
    x = np.asarray(scores, dtype=float)
    x = x - np.max(x)
    e = np.exp(x)
    return e / e.sum()


def z_col(
    df: pd.DataFrame,
    col: str,
    label: str,
    neg: bool = False,
    drop: bool = False,
) -> pd.DataFrame:
    new_col = df.apply(lambda row: (row[col] - df[col].mean()) / df[col].std(), axis=1)
    df.insert(df.columns.get_loc(col) + 1, label, new_col)
    if drop:
        df.drop(columns=[label], inplace=True)
    if neg:
        df[label] = -df[label]
    return df


zCol = z_col


def analytic(
    df: pd.DataFrame,
    index_col: str,
    cols: list[str],
    weights: list[float],
    label: str,
) -> pd.DataFrame:
    base = pd.DataFrame()
    base["0"] = [0] * len(df)
    for i in range(len(weights)):
        base["0"] = base["0"] + df[cols[i]] * weights[i]
    base["0"] = -base["0"]
    df.insert(df.columns.get_loc(index_col) + 1, label, base["0"])
    return df
