import { scans } from "@/lib/lm-scans";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  let scanId = "";
  try {
    const body = (await req.json()) as { scanId?: string };
    scanId = (body.scanId ?? "").trim();
  } catch {
    return Response.json({ error: "طلب غير صالح" }, { status: 400 });
  }
  const child = scans.get(scanId);
  if (!child) {
    return Response.json({ ok: false, error: "لا توجد عملية مسح بهذا المعرف" }, { status: 404 });
  }
  try {
    child.kill("SIGTERM");
    setTimeout(() => {
      try {
        if (!child.killed) child.kill("SIGKILL");
      } catch {
        /* noop */
      }
    }, 2000);
  } catch {
    /* noop */
  }
  return Response.json({ ok: true });
}
