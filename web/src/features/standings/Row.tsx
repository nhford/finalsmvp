import { Fragment } from "react";
import type { SortKey, ViewMode, YearRow } from "@/types/finals";
import { displayPlayer, displayShare } from "@/lib/sort";
import ExpandedRow from "./ExpandedRow";

interface Props {
  row: YearRow;
  view: ViewMode;
  sortKey: SortKey;
  expanded: string;
  setExpanded: (rowId: string) => void;
}

function cellClass(sortKey: SortKey, key: SortKey, correct: boolean, extra = "") {
  const sorted = sortKey === key;
  return [
    "py-4",
    sorted && correct ? "bg-neutral-200" : "",
    sorted && !correct ? "bg-rose-200/80" : "",
    extra,
  ]
    .filter(Boolean)
    .join(" ");
}

export default function Row({
  row,
  view,
  sortKey,
  expanded,
  setExpanded,
}: Props) {
  const rowId = String(row.year);
  const isExpanded = expanded === rowId;
  const player = displayPlayer(row, view);
  const share = displayShare(row, view);

  const toggleExpanded = () => setExpanded(isExpanded ? "" : rowId);

  return (
    <Fragment>
      <tr
        className={`group border-b border-neutral-600 cursor-pointer transition-colors ${
          row.correct
            ? "bg-white hover:bg-neutral-100"
            : "bg-rose-100/60 hover:bg-rose-200/70"
        }`}
        role="button"
        tabIndex={0}
        aria-expanded={isExpanded}
        aria-label={`${isExpanded ? "Collapse" : "Expand"} details for ${row.year} ${player}`}
        onClick={toggleExpanded}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggleExpanded();
          }
        }}
      >
        <td
          className={cellClass(
            sortKey,
            "year",
            row.correct,
            "text-center text-base md:text-lg font-bold",
          )}
        >
          <span className="md:hidden">
            {`'${(row.year % 100).toString().padStart(2, "0")}`}
          </span>
          <span className="hidden md:block">{row.year}</span>
        </td>
        <td className="py-4 px-0.5 text-center bg-white border-x border-neutral-200">
          {row.logoUrl ? (
            <img
              src={row.logoUrl}
              className="mx-auto w-8 lg:w-14 object-contain"
              alt={row.team}
            />
          ) : (
            <span className="text-xs font-bold">{row.teamAbbr}</span>
          )}
        </td>
        <td
          className={cellClass(
            sortKey,
            "player",
            row.correct,
            "max-w-0 px-1 text-center text-sm md:text-lg font-bold group-hover:underline decoration-black underline-offset-2",
          )}
          title={player}
        >
          <span className="block truncate">{player}</span>
        </td>
        <td
          className={cellClass(
            sortKey,
            "share",
            row.correct,
            "text-center text-base md:text-lg tabular-nums",
          )}
        >
          {share.toFixed(3)}
        </td>
        <td
          className={cellClass(
            sortKey,
            "correct",
            row.correct,
            "text-center text-base md:text-lg",
          )}
        >
          {row.correct ? "Yes" : "No"}
        </td>
      </tr>
      {isExpanded ? <ExpandedRow row={row} view={view} /> : null}
    </Fragment>
  );
}
