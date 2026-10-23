import { spawn } from "child_process";
import { resolveLmDir, resolvePythonCmd } from "@/lib/lm-env";

export const dynamic = "force-dynamic";

const PORT = Number(process.env.LM_DEMO_PORT || 8791);
const SPEC_URL = `http://127.0.0.1:${PORT}/swagger/v1/swagger.json`;

const g = globalThis as unknown as { __lmDemoStarting?: Promise<boolean> | null };

async function mockAlive(): Promise<boolean> {
  try {
    const res = await fetch(SPEC_URL, { signal: AbortSignal.timeout(900), cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function POST() {
  if (!(await mockAlive())) {
    if (!g.__lmDemoStarting) {
      g.__lmDemoStarting = new Promise<boolean>((resolve) => {
        try {
          const child = spawn(resolvePythonCmd(), ["examples/mock_target.py", String(PORT)], {
            cwd: resolveLmDir(),
            stdio: "ignore",
          });
          child.on("error", () => resolve(false));
          child.unref();
        } catch {
          resolve(false);
        }
        // resolve after grace period; readiness double-checked below
        setTimeout(() => resolve(true), 1200);
      }).finally(() => {
        g.__lmDemoStarting = null;
      });
    }
    await g.__lmDemoStarting;

    // poll readiness up to ~5s
    let up = false;
    for (let i = 0; i < 20; i++) {
      if (await mockAlive()) {
        up = true;
        break;
      }
      await new Promise((r) => setTimeout(r, 250));
    }
    if (!up) {
      return Response.json(
        { error: `تعذر تشغيل الهدف التجريبي محليًا (منفذ ${PORT})` },
        { status: 500 }
      );
    }
  }

  return Response.json({
    ok: true,
    specUrl: SPEC_URL,
    baseUrl: `http://127.0.0.1:${PORT}`,
    attackerToken: "Bearer attacker-account-B-session",
    victimIds: [
      { key: "customerId", value: "50770148-258e-4a27-ae08-79257ee70b7f" },
      { key: "employeeId", value: "cff135e7-a737-433b-9d07-93db9249cb64" },
    ],
    note: "هدف وهمي محلي يحوي تسريبًا حقيقيًا + نقطة محمية + فخ إيجابية كاذبة + 404 مقنع",
  });
}
