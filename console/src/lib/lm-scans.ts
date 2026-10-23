import type { ChildProcessWithoutNullStreams } from "child_process";

/** Registry of running LeakMatrix scan processes, shared across route modules. */
const g = globalThis as unknown as {
  __lmScans?: Map<string, ChildProcessWithoutNullStreams>;
};

export const scans: Map<string, ChildProcessWithoutNullStreams> =
  g.__lmScans ?? (g.__lmScans = new Map());
