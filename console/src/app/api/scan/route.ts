import fs from "fs";
import os from "os";
import path from "path";
import { spawn } from "child_process";
import { scans } from "@/lib/lm-scans";
import { resolveLmDir, resolvePythonCmd } from "@/lib/lm-env";

export const dynamic = "force-dynamic";

const MAX_SPEC_BYTES = 3 * 1024 * 1024;
const HARD_KILL_MS = 15 * 60 * 1000;

interface KV {
  key: string;
  value: string;
}

interface ScanBody {
  specUrl?: string;
  specContent?: string;
  baseUrl?: string;
  attackerToken?: string;
  victimToken?: string;
  victimIds?: KV[];
  headers?: KV[];
  contactEmail?: string;
  rps?: number;
  timeout?: number;
  retries?: number;
  race?: number;
  maxVariants?: number;
  strict?: boolean;
  noControls?: boolean;
}

const HTTP_URL = /^https?:\/\/\S+$/i;
const SAFE_TOKEN = /^[^\r\n]{1,8192}$/;
const SAFE_KEY = /^[A-Za-z0-9_\-\.]{1,64}$/;
const SAFE_EMAIL = /^[A-Za-z0-9@._+\-]{3,120}$/;

const clamp = (v: unknown, lo: number, hi: number, dflt: number): number => {
  const n = typeof v === "number" && Number.isFinite(v) ? v : NaN;
  if (Number.isNaN(n)) return dflt;
  return Math.min(hi, Math.max(lo, n));
};

function bad(error: string, status = 400) {
  return Response.json({ error }, { status });
}

export async function POST(req: Request) {
  let body: ScanBody;
  try {
    body = (await req.json()) as ScanBody;
  } catch {
    return bad("طلب غير صالح: JSON غير مقروء");
  }

  const attackerToken = (body.attackerToken ?? "").trim();
  if (!attackerToken) return bad("توكن المهاجم (حسابك B) مطلوب");
  if (!SAFE_TOKEN.test(attackerToken)) return bad("توكن المهاجم يحوي أسطرًا غير صالحة");

  const victimToken = (body.victimToken ?? "").trim();
  const victimIds = (body.victimIds ?? [])
    .filter((p) => p && SAFE_KEY.test(p.key?.trim() ?? "") && /^[^\r\n=]{1,256}$/.test(p.value?.trim() ?? ""))
    .map((p) => ({ key: p.key.trim(), value: p.value.trim() }))
    .slice(0, 20);
  if (!victimToken && victimIds.length === 0) {
    return bad("يلزم معرّفات الضحية: توكن ضحية (JWT) أو معرفات صريحة key=value");
  }

  const specContent = (body.specContent ?? "").trim();
  const specUrl = (body.specUrl ?? "").trim();
  let specArg = "";
  let specTmpFile = "";
  if (specContent) {
    if (specContent.length > MAX_SPEC_BYTES) return bad("محتوى المواصفة أكبر من 3MB");
    specArg = specContent;
  } else if (specUrl) {
    if (!HTTP_URL.test(specUrl)) return bad("رابط المواصفة يجب أن يكون http/https صالحًا");
    specArg = specUrl;
  } else {
    return bad("حدد مواصفة OpenAPI/Swagger: رابط أو محتوى ملصوق");
  }

  const baseUrl = (body.baseUrl ?? "").trim();
  if (baseUrl && !HTTP_URL.test(baseUrl)) return bad("Base URL يجب أن يكون http/https صالحًا");

  const extraHeaders = (body.headers ?? [])
    .filter((h) => h && SAFE_KEY.test(h.key?.trim() ?? "") && /^[^\r\n]{0,1024}$/.test(h.value?.trim() ?? ""))
    .map((h) => ({ key: h.key.trim(), value: h.value.trim() }))
    .slice(0, 20);

  const contact = (body.contactEmail ?? "").trim();
  if (contact && !SAFE_EMAIL.test(contact)) return bad("بريد التواصل غير صالح (يُستخدم داخل User-Agent)");
  const userAgent = `LeakMatrix-Console/0.3.0 (authorized-testing; contact=${contact || "unset"})`;

  const rps = clamp(body.rps, 0.2, 10, 4);
  const timeout = Math.round(clamp(body.timeout, 3, 60, 15));
  const retries = Math.round(clamp(body.retries, 0, 5, 2));
  const race = Math.round(clamp(body.race, 0, 8, 0));
  const maxVariants = Math.round(clamp(body.maxVariants, 1, 8, 8));

  const scanId = crypto.randomUUID();

  if (specContent) {
    specTmpFile = path.join(os.tmpdir(), `lm-spec-${scanId}.json`);
    try {
      fs.writeFileSync(specTmpFile, specContent, "utf-8");
    } catch {
      return bad("تعذر حفظ ملف المواصفة المؤقت على الخادم", 500);
    }
  }

  const reportFile = path.join(os.tmpdir(), `lm-report-${scanId}.json`);

  const args = ["-m", "leakmatrix.cli", "run", "--spec", specTmpFile || specArg];
  args.push("--attacker-token", attackerToken);
  if (victimToken) args.push("--victim-token", victimToken);
  for (const p of victimIds) args.push("--victim-ids", `${p.key}=${p.value}`);
  if (baseUrl) args.push("--base-url", baseUrl);
  for (const h of extraHeaders) args.push("--header", `${h.key}: ${h.value}`);
  args.push("--methods", "get");
  args.push("--rps", String(rps));
  args.push("--retries", String(retries));
  args.push("--timeout", String(timeout));
  if (race > 0) args.push("--race", String(race));
  if (body.strict) args.push("--strict");
  if (body.noControls) args.push("--no-controls");
  args.push("--max-variants-per-op", String(maxVariants));
  args.push("--user-agent", userAgent);
  args.push("--json", reportFile);

  let child;
  try {
    child = spawn(resolvePythonCmd(), args, {
      cwd: resolveLmDir(),
      env: { ...process.env, PYTHONUNBUFFERED: "1" },
    });
  } catch (e) {
    return bad(`تعذر تشغيل محرك بايثون: ${String(e)}`, 500);
  }

  scans.set(scanId, child);
  const killTimer = setTimeout(() => {
    try {
      child.kill("SIGKILL");
    } catch {
      /* noop */
    }
  }, HARD_KILL_MS);

  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const send = (obj: unknown) => {
        try {
          controller.enqueue(encoder.encode(JSON.stringify(obj) + "\n"));
        } catch {
          /* client gone */
        }
      };

      send({ t: "started", scanId });

      child.stdout.setEncoding("utf-8");
      child.stdout.on("data", (chunk: string) => {
        for (const line of chunk.split(/\r?\n/)) {
          if (line.trim()) send({ t: "log", line });
        }
      });
      child.stderr.setEncoding("utf-8");
      child.stderr.on("data", (chunk: string) => {
        for (const line of chunk.split(/\r?\n/)) {
          if (line.trim()) send({ t: "err", line });
        }
      });

      const cleanup = () => {
        clearTimeout(killTimer);
        scans.delete(scanId);
        try {
          if (specTmpFile) fs.unlinkSync(specTmpFile);
        } catch {
          /* noop */
        }
      };

      child.on("error", (err) => {
        send({ t: "fatal", message: `فشل تشغيل العملية: ${err.message}` });
        cleanup();
        try {
          controller.close();
        } catch {
          /* noop */
        }
      });

      child.on("close", (code) => {
        let report: unknown = null;
        try {
          const raw = fs.readFileSync(reportFile, "utf-8");
          report = JSON.parse(raw);
          fs.unlinkSync(reportFile);
        } catch {
          report = null;
        }
        send({ t: "done", exitCode: code ?? -1, report });
        cleanup();
        try {
          controller.close();
        } catch {
          /* noop */
        }
      });
    },
    cancel() {
      try {
        child.kill("SIGTERM");
      } catch {
        /* noop */
      }
      clearTimeout(killTimer);
      scans.delete(scanId);
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "application/x-ndjson; charset=utf-8",
      "Cache-Control": "no-store, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}
