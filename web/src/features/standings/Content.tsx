import { Fragment, useMemo, useState } from "react";
import type { FinalsData, GroupBy, ViewMode } from "@/types/finals";
import ControlButton from "@/ui/ControlButton";
import ScrollHintStrip from "@/ui/ScrollHintStrip";
import MvpTable from "./MvpTable";

interface Props {
  data: FinalsData;
}

export default function Content({ data }: Props) {
  const { years, teams, maxYear, minYear } = data;
  const yearList = useMemo(
    () =>
      Array.from({ length: maxYear - minYear + 1 }, (_, i) => maxYear - i),
    [maxYear, minYear],
  );

  const [view, setView] = useState<ViewMode>("predicted");
  const [groupBy, setGroupBy] = useState<GroupBy>("year");
  const [yearFilter, setYearFilter] = useState<number | "all">("all");
  const [team, setTeam] = useState(teams[0] ?? "BOS");

  const filtered = useMemo(() => {
    if (groupBy === "year") {
      if (yearFilter === "all") return years;
      return years.filter((row) => row.year === yearFilter);
    }
    return years.filter((row) => row.teamAbbr === team);
  }, [groupBy, yearFilter, team, years]);

  return (
    <div className="h-full pb-10">
      <div className="flex flex-wrap py-2 gap-2 justify-center items-center">
        <p className="text-sm md:text-base mr-1">view:</p>
        {(
          [
            { key: "predicted", label: "Predicted" },
            { key: "actual", label: "Actual" },
          ] as const
        ).map(({ key, label }) => (
          <ControlButton
            key={key}
            active={view === key}
            size="sm"
            className="w-28"
            onClick={() => setView(key)}
          >
            {label}
          </ControlButton>
        ))}
      </div>

      <div className="flex flex-wrap py-2 gap-2 justify-center items-center">
        <p className="text-sm md:text-base mr-1">group by:</p>
        {(
          [
            { key: "year", label: "Year" },
            { key: "team", label: "Team" },
          ] as const
        ).map(({ key, label }) => (
          <ControlButton
            key={key}
            active={groupBy === key}
            size="sm"
            className="w-20"
            onClick={() => {
              if (groupBy === key) return;
              setGroupBy(key);
            }}
          >
            {label}
          </ControlButton>
        ))}
      </div>

      <div className="flex items-center gap-2 py-2">
        <p className="shrink-0 text-sm md:text-base">filter by:</p>
        <ScrollHintStrip
          className="min-w-0 flex-1"
          label={
            groupBy === "year"
              ? "Scroll for more years"
              : "Scroll for more teams"
          }
        >
          {groupBy === "year" ? (
            <>
              <ControlButton
                size="sm"
                active={yearFilter === "all"}
                className="shrink-0"
                onClick={() => setYearFilter("all")}
              >
                All
              </ControlButton>
              {yearList.map((item, index, items) => {
                const prev = items[index - 1];
                const showDecadeLine =
                  prev != null &&
                  Math.floor(prev / 10) !== Math.floor(item / 10);
                return (
                  <Fragment key={`year_${item}`}>
                    {showDecadeLine ? (
                      <div
                        aria-hidden
                        className="mx-0.5 h-7 w-px shrink-0 self-center bg-white/55"
                      />
                    ) : null}
                    <ControlButton
                      size="sm"
                      active={yearFilter === item}
                      className="shrink-0"
                      onClick={() => setYearFilter(item)}
                    >
                      {item}
                    </ControlButton>
                  </Fragment>
                );
              })}
            </>
          ) : (
            teams.map((abbr) => (
              <ControlButton
                key={abbr}
                size="sm"
                active={team === abbr}
                className="w-14 shrink-0"
                onClick={() => setTeam(abbr)}
              >
                {abbr}
              </ControlButton>
            ))
          )}
        </ScrollHintStrip>
      </div>

      <p className="text-center text-sm text-white/60 mb-2">
        {view === "predicted"
          ? "Showing model pick (highest Finals MVP share) per champion"
          : "Showing actual Finals MVP and their model share"}
      </p>

      <MvpTable view={view} groupBy={groupBy} source={filtered} />
    </div>
  );
}
