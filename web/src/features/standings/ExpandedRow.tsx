import { useState } from "react";
import type { Candidate, ViewMode, YearRow } from "@/types/finals";
import { playerImageUrl } from "@/lib/playerImage";

interface Props {
  row: YearRow;
  view: ViewMode;
}

const DEFAULT_VISIBLE = 5;

function fmt(value: number | null | undefined, digits = 0) {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

function fmtPct(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(3);
}

function ShareBar({ share, highlight }: { share: number; highlight: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-20 md:w-28 rounded bg-neutral-200 overflow-hidden">
        <div
          className={`h-full rounded ${highlight ? "bg-emerald-600" : "bg-neutral-500"}`}
          style={{ width: `${Math.max(2, Math.min(100, share * 100))}%` }}
        />
      </div>
      <span className="tabular-nums text-sm md:text-base w-12 text-right">
        {share.toFixed(3)}
      </span>
    </div>
  );
}

function candidateHighlight(c: Candidate, view: ViewMode) {
  if (view === "predicted") return c.isPredicted;
  return c.isActualMvp;
}

function seriesResult(row: YearRow): string | null {
  // Champions always win; Finals length → 4–0 … 4–3.
  const games = row.candidates[0]?.stats.Series_G;
  if (games == null || games < 4 || games > 7) return null;
  return `4–${games - 4}`;
}

export default function ExpandedRow({ row, view }: Props) {
  const [showAll, setShowAll] = useState(false);
  const disagree = !row.correct;
  const hasMore = row.candidates.length > DEFAULT_VISIBLE;
  const visible = showAll
    ? row.candidates
    : row.candidates.slice(0, DEFAULT_VISIBLE);
  const hiddenCount = row.candidates.length - DEFAULT_VISIBLE;
  const result = seriesResult(row);

  return (
    <tr id={`expanded-${row.year}`} className="bg-neutral-50">
      <td colSpan={5} className="px-3 py-4 md:px-5">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col md:flex-row md:items-start gap-3 md:gap-6">
            <div className="flex items-center gap-3 shrink-0">
              {row.logoUrl ? (
                <img
                  src={row.logoUrl}
                  alt=""
                  className="w-14 h-14 md:w-20 md:h-20 object-contain"
                />
              ) : null}
              <div>
                <p className="font-bold text-base md:text-lg">{row.team}</p>
                <p className="text-sm text-neutral-600">
                  {row.year} Finals
                  {row.opponent ? ` vs ${row.opponent}` : ""}
                  {result ? ` · ${result}` : ""}
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm md:text-base flex-1">
              <div className="rounded border border-neutral-200 px-3 py-2">
                <p className="text-neutral-500 text-xs uppercase tracking-wide">
                  Model pick
                </p>
                <p className="font-bold">{row.predictedPlayer}</p>
                <p className="tabular-nums">{row.predictedShare.toFixed(3)} share</p>
              </div>
              <div className="rounded border border-neutral-200 px-3 py-2">
                <p className="text-neutral-500 text-xs uppercase tracking-wide">
                  Actual MVP
                </p>
                <p className="font-bold">{row.actualPlayer}</p>
                <p className="tabular-nums">{row.actualShare.toFixed(3)} share</p>
              </div>
            </div>
          </div>

          {disagree ? (
            <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2">
              Model disagreed: picked {row.predictedPlayer} (
              {row.predictedShare.toFixed(3)}) over {row.actualPlayer} (
              {row.actualShare.toFixed(3)}).
            </p>
          ) : null}

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs md:text-sm">
              <thead>
                <tr className="border-b border-neutral-300 text-neutral-600">
                  <th className="py-2 pr-2 font-semibold">Player</th>
                  <th className="py-2 pr-2 font-semibold">Share</th>
                  <th className="py-2 px-1 font-semibold text-right">PTS</th>
                  <th className="py-2 px-1 font-semibold text-right">TRB</th>
                  <th className="py-2 px-1 font-semibold text-right">AST</th>
                  <th className="py-2 px-1 font-semibold text-right hidden sm:table-cell">
                    USG%
                  </th>
                  <th className="py-2 px-1 font-semibold text-right hidden md:table-cell">
                    NetRtg
                  </th>
                  <th className="py-2 px-1 font-semibold text-right hidden lg:table-cell">
                    FG%
                  </th>
                  <th className="py-2 pl-1 font-semibold text-right hidden lg:table-cell">
                    MP
                  </th>
                </tr>
              </thead>
              <tbody>
                {visible.map((c) => {
                  const highlight = candidateHighlight(c, view);
                  const headshot = playerImageUrl(
                    row.year,
                    row.teamAbbr,
                    c.player,
                  );
                  return (
                    <tr
                      key={`${row.year}_${c.player}`}
                      className={`border-b border-neutral-200 last:border-0 ${
                        highlight ? "bg-emerald-50" : ""
                      } ${c.isActualMvp && !highlight ? "bg-sky-50" : ""}`}
                    >
                      <td className="py-2 pr-2 font-medium whitespace-nowrap">
                        <span className="inline-flex items-center gap-2">
                          <img
                            src={headshot}
                            alt=""
                            role="presentation"
                            className="h-8 w-8 object-contain shrink-0"
                          />
                          <span>
                            {c.player}
                            {c.isActualMvp ? (
                              <span className="ml-1 text-[10px] uppercase text-sky-700">
                                MVP
                              </span>
                            ) : null}
                            {c.isPredicted ? (
                              <span className="ml-1 text-[10px] uppercase text-emerald-700">
                                Pick
                              </span>
                            ) : null}
                          </span>
                        </span>
                      </td>
                      <td className="py-2 pr-2">
                        <ShareBar share={c.mvpShare} highlight={highlight} />
                      </td>
                      <td className="py-2 px-1 text-right tabular-nums">
                        {fmt(c.stats.PTS)}
                      </td>
                      <td className="py-2 px-1 text-right tabular-nums">
                        {fmt(c.stats.TRB)}
                      </td>
                      <td className="py-2 px-1 text-right tabular-nums">
                        {fmt(c.stats.AST)}
                      </td>
                      <td className="py-2 px-1 text-right tabular-nums hidden sm:table-cell">
                        {fmt(c.stats["USG%"], 1)}
                      </td>
                      <td className="py-2 px-1 text-right tabular-nums hidden md:table-cell">
                        {fmt(c.stats.NetRtg, 1)}
                      </td>
                      <td className="py-2 px-1 text-right tabular-nums hidden lg:table-cell">
                        {fmtPct(c.stats["FG%"])}
                      </td>
                      <td className="py-2 pl-1 text-right tabular-nums hidden lg:table-cell">
                        {fmt(c.stats.MP)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {hasMore ? (
            <button
              type="button"
              className="self-center rounded border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium text-neutral-800 transition-colors hover:bg-neutral-100"
              onClick={() => setShowAll((prev) => !prev)}
            >
              {showAll
                ? "Show less"
                : `Show ${hiddenCount} more`}
            </button>
          ) : null}
        </div>
      </td>
    </tr>
  );
}
