import type { SortKey, YearRow } from "@/types/finals";

export function displayPlayer(row: YearRow, view: "predicted" | "actual") {
  return view === "predicted" ? row.predictedPlayer : row.actualPlayer;
}

export function displayShare(row: YearRow, view: "predicted" | "actual") {
  return view === "predicted" ? row.predictedShare : row.actualShare;
}

function sortValue(
  row: YearRow,
  key: SortKey,
  view: "predicted" | "actual",
): string | number | boolean {
  switch (key) {
    case "year":
      return row.year;
    case "team":
      return row.teamAbbr || row.team;
    case "player":
      return displayPlayer(row, view);
    case "share":
      return displayShare(row, view);
    case "correct":
      return row.correct;
  }
}

export function sortRows(
  rows: YearRow[],
  key: SortKey,
  dir: "asc" | "desc",
  view: "predicted" | "actual",
): YearRow[] {
  const factor = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const av = sortValue(a, key, view);
    const bv = sortValue(b, key, view);
    if (typeof av === "string" && typeof bv === "string") {
      return av.localeCompare(bv) * factor;
    }
    if (av < bv) return -1 * factor;
    if (av > bv) return 1 * factor;
    return b.year - a.year;
  });
}

export function toggleSort(
  current: { key: SortKey; dir: "asc" | "desc" },
  key: SortKey,
  natural: "asc" | "desc" = "asc",
): { key: SortKey; dir: "asc" | "desc" } {
  if (current.key !== key) {
    return { key, dir: natural };
  }
  return { key, dir: current.dir === "asc" ? "desc" : "asc" };
}
