import { useMemo, useState } from "react";
import type { FinalsData, GroupBy, ViewMode } from "@/types/finals";
import ControlButton from "@/ui/ControlButton";
import ScrollHintStrip from "@/ui/ScrollHintStrip";
import MvpTable from "./MvpTable";

interface Props {
  data: FinalsData;
}

function decadeStart(year: number) {
  return Math.floor(year / 10) * 10;
}

function decadeLabel(start: number) {
  return `${start}s`;
}

export default function Content({ data }: Props) {
  const { years, teams, maxYear, minYear } = data;
  const decades = useMemo(() => {
    const maxDecade = decadeStart(maxYear);
    const minDecade = decadeStart(minYear);
    const list: number[] = [];
    for (let d = maxDecade; d >= minDecade; d -= 10) list.push(d);
    return list;
  }, [maxYear, minYear]);

  const [view, setView] = useState<ViewMode>("predicted");
  const [groupBy, setGroupBy] = useState<GroupBy>("year");
  const [decadeFilter, setDecadeFilter] = useState<number | "all">("all");
  const [team, setTeam] = useState(teams[0] ?? "BOS");

  const filtered = useMemo(() => {
    if (groupBy === "year") {
      if (decadeFilter === "all") return years;
      return years.filter((row) => decadeStart(row.year) === decadeFilter);
    }
    return years.filter((row) => row.teamAbbr === team);
  }, [groupBy, decadeFilter, team, years]);

  return (
    <div className="h-full pb-10">
      <div className="flex flex-wrap py-2 gap-x-6 gap-y-2 justify-center items-center">
        <div className="flex flex-wrap gap-2 items-center">
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
        <div className="flex flex-wrap gap-2 items-center">
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
      </div>

      <div className="flex items-center gap-2 py-2">
        <p className="shrink-0 text-sm md:text-base">filter by:</p>
        <ScrollHintStrip
          className="min-w-0 flex-1"
          label={
            groupBy === "year"
              ? "Scroll for more decades"
              : "Scroll for more teams"
          }
        >
          {groupBy === "year" ? (
            <>
              <ControlButton
                size="sm"
                active={decadeFilter === "all"}
                className="shrink-0"
                onClick={() => setDecadeFilter("all")}
              >
                All
              </ControlButton>
              {decades.map((start) => (
                <ControlButton
                  key={`decade_${start}`}
                  size="sm"
                  active={decadeFilter === start}
                  className="shrink-0"
                  onClick={() => setDecadeFilter(start)}
                >
                  {decadeLabel(start)}
                </ControlButton>
              ))}
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
