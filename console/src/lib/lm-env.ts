import fs from "fs";
import path from "path";
import { spawnSync } from "child_process";

/**
 * يتحقق من أن المجلد يحتوي حزمة leakmatrix (مفتاح: leakmatrix/cli.py)
 */
function looksLikeLmHome(dir: string): boolean {
  try {
    return fs.existsSync(path.join(dir, "leakmatrix", "cli.py"));
  } catch {
    return false;
  }
}

/**
 * يحدد مجلد أداة LeakMatrix (الذي يُشغَّل منه `python -m leakmatrix.cli`).
 * ترتيب الأولوية:
 *  1. متغير البيئة LEAKMATRIX_HOME
 *  2. المجلد الأب لمجلد الواجهة (عند سحب المستودع كاملًا: repo/console → repo)
 *  3. مسار بيئة التطوير الافتراضية
 */
export function resolveLmDir(): string {
  const candidates = [
    process.env.LEAKMATRIX_HOME?.trim(),
    path.resolve(process.cwd(), ".."),
    "/home/z/my-project/download/leakmatrix",
  ].filter((c): c is string => Boolean(c));

  for (const c of candidates) {
    if (looksLikeLmHome(c)) return c;
  }
  return candidates[0];
}

let cachedPython: string | null = null;

/**
 * يفضّل python3، ويرجع إلى python (ويندوز عادةً).
 * يُكتشف مرة واحدة ثم يُخزَّن.
 */
export function resolvePythonCmd(): string {
  if (cachedPython) return cachedPython;
  for (const cmd of ["python3", "python"]) {
    try {
      const r = spawnSync(cmd, ["-c", "print(1)"], { timeout: 8000 });
      if (r.status === 0) {
        cachedPython = cmd;
        return cmd;
      }
    } catch {
      /* جرب التالي */
    }
  }
  cachedPython = "python3";
  return cachedPython;
}
