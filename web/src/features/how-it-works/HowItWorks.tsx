import { useState, type ReactNode } from "react";
import type { FeatureWeight } from "@/types/finals";

interface Props {
  featureWeights: FeatureWeight[];
  correct: number;
  total: number;
  minYear: number;
  maxYear: number;
}

const SIGNALS = [
  { label: "Model", value: "Logistic regression" },
  { label: "Features", value: "15 lean series stats" },
  { label: "Output", value: "Softmax MVP share" },
] as const;

const USE_STEPS = [
  "Browse by year or champion team; filter the standings strip.",
  "Toggle Predicted vs Actual to compare the model pick and the award.",
  "Expand a row for the full top-8 share stack and series box stats.",
] as const;

const FEATURE_BLURBS: Record<string, string> = {
  "USG%": "Usage rate — how much offense runs through the player",
  PTS: "Series points",
  PTS_CV: "Per-game points volatility (std / mean) — lower is steadier",
  "FG%": "Field-goal percentage",
  ORtg: "Offensive rating",
  "rel_Q4_eFG%": "Clutch Q4 relative effective FG%",
  "rel_WL_eFG%": "eFG% in team wins minus eFG% in team losses",
  "3P%": "Three-point percentage",
  MP: "Minutes played",
  AST: "Assists",
  TRB: "Total rebounds",
  TOV: "Turnovers (negative weight helps)",
  GM: "Games missed in the series",
  STL: "Steals",
  BLK: "Blocks",
  DRtg: "Defensive rating (lower is better; negative coef)",
};

function WeightBar({ weight, maxAbs }: { weight: number; maxAbs: number }) {
  const pct = maxAbs > 0 ? (Math.abs(weight) / maxAbs) * 100 : 0;
  const positive = weight >= 0;
  return (
    <div className="flex items-center gap-2 min-w-0">
      <div className="h-2 flex-1 rounded bg-white/10 overflow-hidden">
        <div
          className={`h-full rounded ${positive ? "bg-emerald-500" : "bg-rose-500"}`}
          style={{ width: `${Math.max(3, pct)}%` }}
        />
      </div>
      <span
        className={`tabular-nums text-xs md:text-sm w-12 text-right shrink-0 ${
          positive ? "text-emerald-300" : "text-rose-300"
        }`}
      >
        {weight > 0 ? "+" : ""}
        {weight.toFixed(2)}
      </span>
    </div>
  );
}

export default function HowItWorks({
  featureWeights,
  correct,
  total,
  minYear,
  maxYear,
}: Props) {
  const [openId, setOpenId] = useState<string | null>("weights");
  const maxAbs = Math.max(...featureWeights.map((f) => Math.abs(f.weight)), 0);

  const DETAILS: { id: string; title: string; body: ReactNode }[] = [
    {
      id: "weights",
      title: "Feature weights",
      body: (
        <div className="space-y-3">
          <p>
            Standardized logistic coefficients from the last out-of-fold fold.
            Positive weights push MVP share up; negative weights push it down
            (after scaling each feature).
          </p>
          {featureWeights.length === 0 ? (
            <p className="text-white/55">
              Weights unavailable — run{" "}
              <code className="text-white/80">scripts/build_ml_output.py</code>{" "}
              then rebuild frontend data.
            </p>
          ) : (
            <ul className="space-y-2">
              {featureWeights.map(({ name, weight }) => (
                <li key={name}>
                  <div className="flex items-baseline justify-between gap-2 mb-0.5">
                    <span className="font-semibold text-white tabular-nums">
                      {name}
                    </span>
                    <span className="text-xs text-white/45 truncate hidden sm:inline">
                      {FEATURE_BLURBS[name] ?? ""}
                    </span>
                  </div>
                  <WeightBar weight={weight} maxAbs={maxAbs} />
                </li>
              ))}
            </ul>
          )}
        </div>
      ),
    },
    {
      id: "drivers",
      title: "What drives the prediction?",
      body: (
        <>
          Each champion Finals top-8 scorer is scored with a lean box-score set
          (usage, points, shooting, counting stats, minutes, games missed) plus
          advanced{" "}
          <span className="text-white/90">USG%</span>,{" "}
          <span className="text-white/90">ORtg</span>, and{" "}
          <span className="text-white/90">DRtg</span> from 1984 on. Class
          imbalance is handled with SMOTE inside each training fold; player
          probabilities are out-of-fold, then softmaxed within the year into an
          MVP share.
        </>
      ),
    },
    {
      id: "limits",
      title: "How accurate is it?",
      body: (
        <>
          The model matches the actual Finals MVP in {correct}/{total} years (
          {minYear}–{maxYear}). It is strongest when one star clearly leads
          scoring and usage; it can miss narrative or defensive awards and years
          with two near-equal candidates.
        </>
      ),
    },
    {
      id: "stack",
      title: "How is this built?",
      body: (
        <>
          Series tables come from Basketball-Reference. Feature engineering and
          the OOF logistic live in the repo notebook and{" "}
          <code className="text-white/80">scripts/build_ml_output.py</code>; this
          page reads the generated JSON standings.
        </>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <p className="text-sm md:text-base text-white/85 text-center md:text-left leading-relaxed">
        Estimate who should have won NBA Finals MVP from champion series box
        scores, and compare that pick to the actual award.
      </p>

      <dl className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-white/20 rounded border border-white/25 overflow-hidden">
        {SIGNALS.map(({ label, value }) => (
          <div
            key={label}
            className="bg-neutral-800 px-3 py-3 text-center sm:text-left"
          >
            <dt className="text-xs uppercase tracking-wide text-white/50">
              {label}
            </dt>
            <dd className="mt-1 text-sm md:text-base font-semibold text-white">
              {value}
            </dd>
          </div>
        ))}
      </dl>

      <div>
        <h3 className="text-sm md:text-base font-semibold text-white mb-2">
          How to read this page
        </h3>
        <ol className="space-y-1.5 text-sm md:text-base text-white/80 list-decimal list-inside">
          {USE_STEPS.map((step) => (
            <li key={step} className="leading-snug">
              {step}
            </li>
          ))}
        </ol>
      </div>

      <div className="border-t border-white/20">
        {DETAILS.map(({ id, title, body }) => {
          const open = openId === id;
          return (
            <div key={id} className="border-b border-white/20">
              <button
                type="button"
                aria-expanded={open}
                onClick={() => setOpenId(open ? null : id)}
                className="flex w-full items-center justify-between gap-3 py-3 text-left text-sm md:text-base font-semibold text-white transition-colors hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
              >
                <span>{title}</span>
                <span
                  className="shrink-0 text-white/55 text-lg leading-none"
                  aria-hidden
                >
                  {open ? "−" : "+"}
                </span>
              </button>
              {open ? (
                <div className="pb-3 text-sm md:text-base text-white/75 leading-relaxed">
                  {body}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
