import { useEffect, useState } from "react";
import type { SortKey, ViewMode, YearRow } from "@/types/finals";
import ControlButton from "@/ui/ControlButton";
import { sortRows, toggleSort } from "@/lib/sort";
import Row from "./Row";

const PAGE_SIZE = 10;

interface Props {
  view: ViewMode;
  groupBy: "year" | "team";
  source: YearRow[];
}

function pageNumbers(current: number, total: number): (number | "…")[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages = new Set<number>([1, total, current]);
  for (let i = current - 1; i <= current + 1; i++) {
    if (i >= 1 && i <= total) pages.add(i);
  }

  const sorted = [...pages].sort((a, b) => a - b);
  const result: (number | "…")[] = [];
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] > 1) result.push("…");
    result.push(sorted[i]);
  }
  return result;
}

export default function MvpTable({ view, groupBy, source }: Props) {
  const [rows, setRows] = useState<YearRow[]>(source);
  const [sorted, setSorted] = useState<{ key: SortKey; dir: "asc" | "desc" }>({
    key: groupBy === "team" ? "year" : "year",
    dir: "desc",
  });
  const [expanded, setExpanded] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const next = sortRows(source, "year", "desc", view);
    setRows(next);
    setSorted({ key: "year", dir: "desc" });
    setPage(1);
    setExpanded("");
  }, [groupBy, source, view]);

  const total = rows.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const start = (currentPage - 1) * PAGE_SIZE;
  const pageRows = rows.slice(start, start + PAGE_SIZE);

  const playerLabel = view === "predicted" ? "Predicted" : "Actual MVP";
  const shareLabel = view === "predicted" ? "Share" : "Share";

  return (
    <div className="w-full">
      <div className="w-full overflow-x-auto">
        <table className="w-full table-fixed text-left bg-white text-black rounded-lg">
          <colgroup>
            <col className="w-12 md:w-16 lg:w-20" />
            <col className="w-10 md:w-16 lg:w-20" />
            <col />
            <col className="w-16 md:w-24" />
            <col className="w-14 md:w-20" />
          </colgroup>
          <thead>
            <tr className="text-base md:text-lg border-b">
              {(
                [
                  { key: "year" as const, label: "Year", natural: "desc" as const },
                  { key: "team" as const, label: "Team", natural: "asc" as const },
                  {
                    key: "player" as const,
                    label: playerLabel,
                    natural: "asc" as const,
                  },
                  {
                    key: "share" as const,
                    label: shareLabel,
                    natural: "desc" as const,
                  },
                  {
                    key: "correct" as const,
                    label: "Correct",
                    natural: "desc" as const,
                  },
                ] as const
              ).map((col) => (
                <th
                  key={col.key}
                  className={`px-1 py-4 whitespace-nowrap text-center cursor-pointer transition-colors hover:bg-neutral-100 hover:underline decoration-black underline-offset-2 ${
                    sorted.key === col.key
                      ? "bg-neutral-200 hover:bg-neutral-300"
                      : ""
                  }`}
                  onClick={() => {
                    const next = toggleSort(sorted, col.key, col.natural);
                    setSorted(next);
                    setRows(sortRows(rows, next.key, next.dir, view));
                    setPage(1);
                  }}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  className="px-1 py-8 text-center text-sm md:text-base text-neutral-500"
                >
                  No results
                </td>
              </tr>
            ) : (
              pageRows.map((row) => (
                <Row
                  key={row.year}
                  row={row}
                  view={view}
                  sortKey={sorted.key}
                  expanded={expanded}
                  setExpanded={setExpanded}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-center text-sm md:text-base text-white/70">
        <span className="rounded px-1.5 py-0.5 text-white bg-emerald-700/80">
          green
        </span>
        {" = model pick matched Finals MVP · "}
        <span className="rounded px-1.5 py-0.5 text-white bg-rose-700/70">
          red
        </span>
        {" = miss"}
      </p>

      {total > 0 ? (
        <div className="mt-2 flex flex-col items-center gap-2">
          <p className="text-sm md:text-base text-white/80">
            Showing {pageRows.length} of {total} results
          </p>
          {totalPages > 1 ? (
            <div className="flex flex-wrap justify-center items-center gap-1.5">
              {pageNumbers(currentPage, totalPages).map((item, index) =>
                item === "…" ? (
                  <span
                    key={`ellipsis_${index}`}
                    className="px-1 text-white/50"
                    aria-hidden
                  >
                    …
                  </span>
                ) : (
                  <ControlButton
                    key={`page_${item}`}
                    size="sm"
                    active={item === currentPage}
                    className="min-w-9 !px-2"
                    onClick={() => setPage(item)}
                  >
                    {item}
                  </ControlButton>
                ),
              )}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
