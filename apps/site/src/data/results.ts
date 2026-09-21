// apps/site/src/data/results.ts
// EXPERIMENT RECORDS, GROUPED AND SUMMARISED AT BUILD TIME.
//
// SHAPED FROM A REAL RECORD. A probe ran track() through FileTracker: each file
// is one seed, named {stamp}-{experiment}-{id}.json, carrying the commit and the
// dataset digest. So five seeds are five files grouped by `experiment`, and the
// ladder's "identical protocol" rule is checkable rather than asserted.
//
// TWO INTERVALS, NOT ONE. The protocol's bootstrap intervals belong inside an
// experiment, resampling test pairs. Across SEEDS, with five values, a
// percentile bootstrap is unreliable; this is the t-interval,
// mean +/- t(0.975, n-1) * s / sqrt(n), and the page labels it as that.
import { readRecords } from "./evidence";
import { experimentRunV1Schema } from "../contracts/experiment-run.v1.gen";

export const PRIMARY_METRIC = "average_precision";
export const REQUIRED_SEEDS = 5;


// Two-sided 95% critical values of Student's t, by degrees of freedom.
const T975: { [df: number]: number } = {
  1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
  8: 2.306, 9: 2.262, 10: 2.228, 15: 2.131, 20: 2.086, 30: 2.042,
};
function tCritical(df: number): number {
  if (T975[df]) return T975[df];
  const known = Object.keys(T975).map(Number).filter((k) => k <= df);
  return known.length ? T975[Math.max(...known)] : 1.96;
}

export type Summary = {
  experiment: string;
  n: number;
  mean: number | null;
  low: number | null;
  high: number | null;
  reproducible: number;
  digests: string[];
  comparable: boolean;
  enoughSeeds: boolean;
};

// Parsed at the trust boundary by the Zod generated from ExperimentRun: a record
// that does not match experiment-run/v1 fails the build rather than a figure.
function completedRuns() {
  return readRecords("experiments", experimentRunV1Schema).filter((r) => r.status === "completed");
}

export function summarise(experiments: string[]): {
  summaries: { [experiment: string]: Summary };
  reference: string | null;
} {
  const records = completedRuns();

  // THE REFERENCE DATASET is the one most records were measured on. A rung on
  // another digest measured something else, and setting it beside the others
  // would compare results the protocol says are not comparable.
  const counts = new Map<string, number>();
  for (const r of records) counts.set(r.dataset_digest, (counts.get(r.dataset_digest) ?? 0) + 1);
  const reference = counts.size
    ? [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0]
    : null;

  const summaries: { [experiment: string]: Summary } = {};
  for (const experiment of experiments) {
    const group = records.filter((r) => r.experiment === experiment);
    const values = group
      .map((r) => r.metrics[PRIMARY_METRIC])
      .filter((v): v is number => typeof v === "number");
    const digests = [...new Set(group.map((r) => r.dataset_digest))];
    const n = values.length;

    let mean: number | null = null, low: number | null = null, high: number | null = null;
    if (n > 0) {
      mean = values.reduce((a, b) => a + b, 0) / n;
      if (n > 1) {
        const m = mean;
        const sd = Math.sqrt(values.reduce((a, v) => a + (v - m) ** 2, 0) / (n - 1));
        const half = tCritical(n - 1) * sd / Math.sqrt(n);
        low = m - half;
        high = m + half;
      }
    }

    summaries[experiment] = {
      experiment, n, mean, low, high,
      reproducible: group.filter((r) => r.working_tree_clean && r.deterministic).length,
      digests,
      comparable: digests.length === 1 && digests[0] === reference,
      enoughSeeds: n >= REQUIRED_SEEDS,
    };
  }
  return { summaries, reference };
}
