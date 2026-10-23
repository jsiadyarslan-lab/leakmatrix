"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Radar,
  ShieldCheck,
  Play,
  Square,
  FlaskConical,
  Eye,
  EyeOff,
  Plus,
  Trash2,
  Download,
  AlertTriangle,
  FileJson,
  FileSpreadsheet,
  ScanSearch,
  Activity,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";

type KV = { key: string; value: string };
type Verdict = {
  operation: string;
  url: string;
  status: number;
  klass: string;
  evidence: string | null;
  elapsed_ms: number;
  secrets: number;
  secret_kinds: string;
};
type Report = {
  tool: string;
  version: string;
  result: "PASS" | "FAIL";
  verdicts: Verdict[];
};
type Msg =
  | { t: "started"; scanId: string }
  | { t: "log"; line: string }
  | { t: "err"; line: string }
  | { t: "done"; exitCode: number; report: Report | null }
  | { t: "fatal"; message: string };

/** Python report emits `class` (reserved word in JS); normalize to `klass`. */
type RawVerdict = Omit<Verdict, "klass"> & { klass?: string; class?: string };
function normalizeReport(raw: Report): Report {
  const verdicts = (raw.verdicts as unknown as RawVerdict[]).map((v) => ({
    ...v,
    klass: v.klass ?? v.class ?? "OTHER",
  }));
  return { ...raw, verdicts };
}

const VERDICT_META: Record<string, { ar: string; chip: string; dot: string; desc: string }> = {
  LEAK: {
    ar: "تسريب مؤكد",
    chip: "bg-red-500/15 text-red-300 border-red-500/40",
    dot: "bg-red-500",
    desc: "جواب 2xx يحوي معرف الضحية داخل الجسم — ثغرة عبور بين المستأجرين مؤكدة",
  },
  RACE_LEAK: {
    ar: "تسريب سباق",
    chip: "bg-rose-500/15 text-rose-300 border-rose-500/40",
    dot: "bg-rose-500",
    desc: "بيانات ضحية وصلت دون استهداف معرفها — درس حادثة OpenAI/redis",
  },
  SUSPECT: {
    ar: "مشتبه",
    chip: "bg-amber-500/15 text-amber-300 border-amber-500/40",
    dot: "bg-amber-400",
    desc: "جواب 2xx كبير بلا مطابقة صريحة للمعرف — يحتاج تمييزًا يدويًا",
  },
  STATIC: {
    ar: "ساكن (فخ قُتل)",
    chip: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
    dot: "bg-emerald-400",
    desc: "نفس الجواب لمعرف عشوائي — النقطة تتجاهل المعرف إطلاقًا",
  },
  BLOCKED: {
    ar: "محجوب",
    chip: "bg-zinc-500/15 text-zinc-300 border-zinc-500/40",
    dot: "bg-zinc-400",
    desc: "401/403 — فحص الصلاحيات يعمل كما يجب",
  },
  NOT_FOUND: {
    ar: "غير موجود",
    chip: "bg-zinc-500/15 text-zinc-300 border-zinc-500/40",
    dot: "bg-zinc-400",
    desc: "404 — إخفاء مقنع أو معرف غير موجود",
  },
  ERROR: {
    ar: "خطأ",
    chip: "bg-orange-500/15 text-orange-300 border-orange-500/40",
    dot: "bg-orange-400",
    desc: "خطأ شبكة أو خادم — أعد المحاولة لاحقًا",
  },
  OTHER: { ar: "أخرى", chip: "bg-zinc-500/15 text-zinc-300 border-zinc-500/40", dot: "bg-zinc-400", desc: "تصنيف غير قياسي" },
};
const ORDER = ["LEAK", "RACE_LEAK", "SUSPECT", "STATIC", "BLOCKED", "NOT_FOUND", "ERROR", "OTHER"];

const PANEL = "bg-[#0c1310] border-[#1c2b25]";
const INPUT_CLS =
  "bg-[#080e0c] border-[#1c2b25] text-zinc-100 placeholder:text-zinc-600 text-sm focus-visible:ring-emerald-500/40";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-zinc-300 text-[13px]">{label}</Label>
      {children}
      {hint ? <p className="text-[11px] leading-relaxed text-zinc-500">{hint}</p> : null}
    </div>
  );
}

function KVEditor({
  items,
  onChange,
  keyPh,
  valPh,
  addLabel,
}: {
  items: KV[];
  onChange: (next: KV[]) => void;
  keyPh: string;
  valPh: string;
  addLabel: string;
}) {
  return (
    <div className="space-y-2">
      {items.map((kv, i) => (
        <div key={i} className="flex items-center gap-2" dir="ltr">
          <Input
            className={`${INPUT_CLS} w-[38%]`}
            placeholder={keyPh}
            value={kv.key}
            onChange={(e) => {
              const next = [...items];
              next[i] = { ...next[i], key: e.target.value };
              onChange(next);
            }}
          />
          <Input
            className={`${INPUT_CLS} flex-1`}
            placeholder={valPh}
            value={kv.value}
            onChange={(e) => {
              const next = [...items];
              next[i] = { ...next[i], value: e.target.value };
              onChange(next);
            }}
          />
          <Button
            variant="ghost"
            size="icon"
            className="text-zinc-500 hover:text-red-400 hover:bg-red-500/10"
            onClick={() => onChange(items.filter((_, j) => j !== i))}
            aria-label="حذف السطر"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <Button
        variant="outline"
        size="sm"
        className="border-[#1c2b25] text-emerald-300 hover:bg-emerald-500/10 hover:text-emerald-200"
        onClick={() => onChange([...items, { key: "", value: "" }])}
      >
        <Plus className="h-3.5 w-3.5" /> {addLabel}
      </Button>
    </div>
  );
}

function SecretInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative" dir="ltr">
      <Input
        type={show ? "text" : "password"}
        className={`${INPUT_CLS} pl-10 font-mono`}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="off"
      />
      <button
        type="button"
        onClick={() => setShow(!show)}
        className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
        aria-label={show ? "إخفاء" : "إظهار"}
      >
        {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}

function StatCard({ k, count }: { k: string; count: number }) {
  const meta = VERDICT_META[k] ?? VERDICT_META.OTHER;
  return (
    <div className={`rounded-lg border ${meta.chip} p-3 flex items-center justify-between`}>
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${meta.dot}`} />
        <span className="text-xs font-medium">{meta.ar}</span>
      </div>
      <span className="text-xl font-bold tabular-nums">{count}</span>
    </div>
  );
}

const csvCell = (s: string) => `"${String(s ?? "").replace(/"/g, '""')}"`;

export default function Home() {
  const [specMode, setSpecMode] = useState<"url" | "paste">("url");
  const [specUrl, setSpecUrl] = useState("");
  const [specContent, setSpecContent] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [attackerToken, setAttackerToken] = useState("");
  const [victimToken, setVictimToken] = useState("");
  const [victimIds, setVictimIds] = useState<KV[]>([{ key: "", value: "" }]);
  const [headers, setHeaders] = useState<KV[]>([]);
  const [contactEmail, setContactEmail] = useState("");
  const [rps, setRps] = useState(4);
  const [timeout_, setTimeout_] = useState(15);
  const [retries, setRetries] = useState(2);
  const [race, setRace] = useState(0);
  const [maxVariants, setMaxVariants] = useState(8);
  const [strict, setStrict] = useState(false);
  const [noControls, setNoControls] = useState(false);
  const [authorized, setAuthorized] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [running, setRunning] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [statusMsg, setStatusMsg] = useState("");
  const [scanId, setScanId] = useState("");
  const [demoInfo, setDemoInfo] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const termRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight;
  }, [logs]);

  const hasVictim =
    victimToken.trim().length > 0 || victimIds.some((v) => v.key.trim() && v.value.trim());
  const hasSpec = specMode === "url" ? specUrl.trim().length > 0 : specContent.trim().length > 0;
  const canRun = authorized && !running && attackerToken.trim().length > 0 && hasVictim && hasSpec;

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const k of ORDER) c[k] = 0;
    if (report) for (const v of report.verdicts) c[v.klass] = (c[v.klass] ?? 0) + 1;
    return c;
  }, [report]);

  const progress = useMemo(() => {
    for (let i = logs.length - 1; i >= 0; i--) {
      const m = logs[i].match(/\[(\d+)\/(\d+)\]/);
      if (m) return { i: Number(m[1]), n: Number(m[2]) };
    }
    return null;
  }, [logs]);

  function handleMsg(msg: Msg) {
    if (msg.t === "started") {
      setScanId(msg.scanId);
    } else if (msg.t === "log" || msg.t === "err") {
      setLogs((prev) => [...prev.slice(-600), msg.t === "err" ? `[stderr] ${msg.line}` : msg.line]);
    } else if (msg.t === "fatal") {
      setLogs((prev) => [...prev, `[fatal] ${msg.message}`]);
      setStatusMsg("فشل المسح");
      setRunning(false);
    } else if (msg.t === "done") {
      setReport(msg.report ? normalizeReport(msg.report) : null);
      setStatusMsg(
        msg.report
          ? msg.report.result === "FAIL"
            ? "النتيجة: FAIL — اكتُشفت تسريبات"
            : "النتيجة: PASS — لا تسريبات مؤكدة"
          : `انتهى المسح برمز خروج ${msg.exitCode} (بلا تقرير JSON)`
      );
      setRunning(false);
    }
  }

  async function runScan() {
    setLogs([]);
    setReport(null);
    setStatusMsg("جارٍ تشغيل محرك LeakMatrix…");
    setRunning(true);
    setScanId("");
    const ac = new AbortController();
    abortRef.current = ac;
    try {
      const res = await fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: ac.signal,
        body: JSON.stringify({
          specUrl: specMode === "url" ? specUrl.trim() : "",
          specContent: specMode === "paste" ? specContent : "",
          baseUrl: baseUrl.trim(),
          attackerToken: attackerToken.trim(),
          victimToken: victimToken.trim(),
          victimIds: victimIds.filter((v) => v.key.trim() && v.value.trim()),
          headers: headers.filter((h) => h.key.trim()),
          contactEmail: contactEmail.trim(),
          rps, timeout: timeout_, retries, race, maxVariants, strict, noControls,
        }),
      });
      if (!res.ok || !res.body) {
        const j = await res.json().catch(() => null);
        setStatusMsg(j?.error ?? "فشل بدء المسح");
        setRunning(false);
        return;
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const ln of lines) {
          if (!ln.trim()) continue;
          try {
            handleMsg(JSON.parse(ln) as Msg);
          } catch {
            /* ignore malformed line */
          }
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setStatusMsg(`انقطاع الاتصال أثناء المسح: ${String(e)}`);
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }

  async function stopScan() {
    abortRef.current?.abort();
    if (scanId) {
      await fetch("/api/scan/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scanId }),
      }).catch(() => null);
    }
    setRunning(false);
    setStatusMsg("أُوقف المسح يدويًا");
  }

  async function loadDemo() {
    setDemoInfo("جارٍ تجهيز الهدف التجريبي…");
    try {
      const res = await fetch("/api/demo", { method: "POST" });
      const j = await res.json();
      if (!res.ok || !j.ok) {
        setDemoInfo(j?.error ?? "فشل تجهيز الهدف التجريبي");
        return;
      }
      setSpecMode("url");
      setSpecUrl(j.specUrl);
      setSpecContent("");
      setBaseUrl(j.baseUrl);
      setAttackerToken(j.attackerToken);
      setVictimToken("");
      setVictimIds(j.victimIds);
      setDemoInfo("تم تحميل إعداد الهدف التجريبي المحلي — اضغط ابدأ المسح");
    } catch {
      setDemoInfo("تعذر الاتصال بخدمة الهدف التجريبي");
    }
  }

  function exportJson() {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "leakmatrix-report.json";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function exportCsv() {
    if (!report) return;
    const head = "operation,url,status,class,evidence,elapsed_ms,secrets,secret_kinds";
    const rows = report.verdicts.map((v) =>
      [v.operation, v.url, v.status, v.klass, v.evidence ?? "", v.elapsed_ms, v.secrets, v.secret_kinds]
        .map((c) => csvCell(String(c)))
        .join(",")
    );
    const blob = new Blob(["\uFEFF" + head + "\n" + rows.join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "leakmatrix-report.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div className="min-h-screen flex flex-col bg-[#070b09] text-zinc-100">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-[#1c2b25] bg-[#070b09]/90 backdrop-blur">
        <div className="mx-auto max-w-7xl px-4 h-14 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="h-8 w-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
              <Radar className="h-4.5 w-4.5 text-emerald-400" />
            </span>
            <div className="leading-tight">
              <div className="flex items-center gap-2">
                <span className="font-bold tracking-tight">LeakMatrix</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-mono" dir="ltr">
                  v0.3.0
                </span>
              </div>
              <span className="text-[11px] text-zinc-500">وحدة تحكم اختبار العبور الأفقي</span>
            </div>
          </div>
          <a
            href="https://github.com/jsiadyarslan-lab/leakmatrix"
            target="_blank"
            rel="noreferrer"
            className="text-xs text-zinc-400 hover:text-emerald-300 transition-colors flex items-center gap-1.5"
          >
            <ScanSearch className="h-3.5 w-3.5" />
            المستودع على GitHub
          </a>
        </div>
      </header>

      <main className="flex-1 mx-auto w-full max-w-7xl px-4 py-6 space-y-6">
        {/* Ethics gate */}
        <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-4">
          <div className="flex items-start gap-3">
            <ShieldCheck className="h-5 w-5 text-emerald-400 mt-0.5 shrink-0" />
            <div className="space-y-1">
              <p className="font-semibold text-emerald-200 text-sm">أداة اختبار مصرّح به — GET فقط، معدل محدود</p>
              <p className="text-[12px] leading-relaxed text-zinc-400">
                LeakMatrix يرسل طلبات GET قراءة فقط بمعدل افتراضي 4 طلبات/ثانية مع إعادة محاولة مؤدبة على 429.
                استخدمه فقط على أهداف لديك تفويض مكتوب بها (برنامج Bug Bounty رسمي مثل Intigriti، أو أنظمتك الخاصة).
              </p>
            </div>
          </div>
        </div>

        {/* How it works */}
        <details className="group rounded-xl border border-[#1c2b25] bg-[#0c1310] p-4">
          <summary className="flex items-center justify-between cursor-pointer list-none select-none">
            <span className="flex items-center gap-2 text-sm font-semibold text-zinc-200">
              <Activity className="h-4 w-4 text-emerald-400" />
              كيف تعمل الأداة؟ (خط الأنابيب والتصنيفات)
            </span>
            <ChevronDown className="h-4 w-4 text-zinc-500 group-open:hidden" />
            <ChevronUp className="h-4 w-4 text-zinc-500 hidden group-open:block" />
          </summary>
          <Separator className="my-4 bg-[#1c2b25]" />
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5 text-[12px] leading-relaxed">
            {[
              ["1. تحليل المواصفة", "يقرأ OpenAPI/Swagger (JSON أو YAML) ويستخرج كل عمليات GET ذات معاملات مسار شبيهة بالمعرفات، ويحل مراجع $ref."],
              ["2. استخراج الهويات", "يفك توكن الضحية (JWT بلا تحقق توقيع) ويسحب customer_id وcompany_id وsub وغيرها، أو تأخذ معرفات صريحة يدويًا."],
              ["3. بناء المصفوفة", "يقابل كل معامل مسار بأقرب معرف ضحية (مطابقة أسماء ذكية) ويسجّل طلبًا لكل ثنائي (عملية، معرف)."],
              ["4. تنفيذ مؤدب", "GET فقط، حد RPS، إعادة محاولة على 429/502/503/504 مع احترام Retry-After، وUser-Agent يعرّف عنك."],
              ["5. تصنيف ذكي", "لكل تسريب مشتبه يطلق طلب تحكم بمعرف عشوائي: إن طابق الجواب نفسه فالنقطة تتجاهل المعرف — تُقتل الإيجابية الكاذبة."],
            ].map(([t, d]) => (
              <div key={t} className="rounded-lg border border-[#1c2b25] bg-[#080e0c] p-3">
                <p className="font-semibold text-emerald-300 mb-1">{t}</p>
                <p className="text-zinc-400">{d}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {ORDER.map((k) => (
              <span
                key={k}
                title={VERDICT_META[k].desc}
                className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] cursor-help ${VERDICT_META[k].chip}`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${VERDICT_META[k].dot}`} />
                {VERDICT_META[k].ar}
              </span>
            ))}
          </div>
        </details>

        <div className="grid gap-6 lg:grid-cols-[440px_1fr] items-start">
          {/* Config column */}
          <Card className={`${PANEL} text-zinc-100`}>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <ScanSearch className="h-4 w-4 text-emerald-400" />
                إعداد المسح
              </CardTitle>
              <CardDescription className="text-zinc-500 text-[12px]">
                مواصفة الهدف + هوية المهاجم + معرفات الضحية = مصفوفة اختبار
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* ROE checkbox */}
              <div
                className={`rounded-lg border p-3 transition-colors ${
                  authorized ? "border-emerald-500/50 bg-emerald-500/5" : "border-[#1c2b25] bg-[#080e0c]"
                }`}
              >
                <label className="flex items-start gap-2.5 cursor-pointer">
                  <Checkbox
                    checked={authorized}
                    onCheckedChange={(v) => setAuthorized(v === true)}
                    className="mt-0.5 border-zinc-500 data-[state=checked]:bg-emerald-500 data-[state=checked]:border-emerald-500"
                  />
                  <span className="text-[12px] leading-relaxed text-zinc-300">
                    أُقر أنني مفوّض باختبار هذا الهدف (برنامج باونتي رسمي أو ملكية خاصة)، وألتزم بحدود النطاق والمعدل،
                    وأتحمل مسؤولية أي استخدام خارج التفويض.
                  </span>
                </label>
              </div>

              <Button
                variant="outline"
                className="w-full border-[#1c2b25] text-amber-300 hover:bg-amber-500/10 hover:text-amber-200"
                onClick={loadDemo}
              >
                <FlaskConical className="h-4 w-4" />
                تحميل إعداد الهدف التجريبي الآمن (محلي)
              </Button>
              {demoInfo ? <p className="text-[11px] text-amber-300/90 -mt-3">{demoInfo}</p> : null}

              <Tabs value={specMode} onValueChange={(v) => setSpecMode(v as "url" | "paste")}>
                <TabsList className="bg-[#080e0c] border border-[#1c2b25] w-full">
                  <TabsTrigger value="url" className="flex-1 data-[state=active]:bg-emerald-500/15 data-[state=active]:text-emerald-300 text-zinc-400">
                    رابط المواصفة
                  </TabsTrigger>
                  <TabsTrigger value="paste" className="flex-1 data-[state=active]:bg-emerald-500/15 data-[state=active]:text-emerald-300 text-zinc-400">
                    لصق المحتوى
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="url" className="pt-3">
                  <Field label="رابط OpenAPI / Swagger (JSON أو YAML)" hint="مثال: https://target/api/swagger/v1/swagger.json">
                    <Input dir="ltr" className={`${INPUT_CLS} font-mono`} placeholder="https://…/swagger.json" value={specUrl} onChange={(e) => setSpecUrl(e.target.value)} />
                  </Field>
                </TabsContent>
                <TabsContent value="paste" className="pt-3">
                  <Field label="محتوى المواصفة (حتى 3MB)">
                    <Textarea dir="ltr" className={`${INPUT_CLS} font-mono min-h-28`} placeholder='{"openapi":"3.0.1", …}' value={specContent} onChange={(e) => setSpecContent(e.target.value)} />
                  </Field>
                </TabsContent>
              </Tabs>

              <Field label="تجاوز Base URL (اختياري)" hint="افتراضيًا يُؤخذ من حقل servers في المواصفة">
                <Input dir="ltr" className={`${INPUT_CLS} font-mono`} placeholder="https://api.target.com" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
              </Field>

              <Field label="توكن المهاجم — حسابك B" hint="ما يُرسل في Authorization. يُستخدم فقط في الذاكرة أثناء المسح ولا يُسجل">
                <SecretInput value={attackerToken} onChange={setAttackerToken} placeholder="Bearer eyJhbGciOi…" />
              </Field>

              <Field label="توكن الضحية — حساب A (اختياري)" hint="يفكّ تلقائيًا لاستخراج المعرفات من الclaims — أو استخدم المعرفات الصريحة أدناه">
                <SecretInput value={victimToken} onChange={setVictimToken} placeholder="Bearer eyJhbGciOi…" />
              </Field>

              <Field label="معرفات الضحية الصريحة" hint="أسماء مطابقة لمعاملات المسار: customerId=… وemployeeId=…">
                <KVEditor items={victimIds} onChange={setVictimIds} keyPh="customerId" valPh="50770148-…" addLabel="إضافة معرف" />
              </Field>

              <Field label="هيدرات إضافية (اختياري)" hint="مثل X-Bug-Bounty: jaber55 — بعض البرامج تشترط تعريفًا">
                <KVEditor items={headers} onChange={setHeaders} keyPh="X-Bug-Bounty" valPh="jaber55" addLabel="إضافة هيدر" />
              </Field>

              <Field label="بريد التواصل (داخل User-Agent)" hint="روح البرامج تطلب هوية — يُرسل كـ contact=… في UA">
                <Input dir="ltr" className={`${INPUT_CLS} font-mono`} placeholder="you@example.com" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} />
              </Field>

              {/* Advanced */}
              <div className="rounded-lg border border-[#1c2b25] bg-[#080e0c]">
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="w-full flex items-center justify-between px-3 py-2.5 text-[13px] text-zinc-300"
                >
                  <span>إعدادات متقدمة</span>
                  {showAdvanced ? <ChevronUp className="h-4 w-4 text-zinc-500" /> : <ChevronDown className="h-4 w-4 text-zinc-500" />}
                </button>
                {showAdvanced ? (
                  <div className="px-3 pb-4 space-y-4">
                    <div>
                      <div className="flex justify-between text-[12px] text-zinc-400 mb-1">
                        <span>حد المعدل (طلب/ثانية)</span>
                        <span className="font-mono text-emerald-300">{rps}</span>
                      </div>
                      <input type="range" min={0.5} max={10} step={0.5} value={rps} onChange={(e) => setRps(Number(e.target.value))} className="w-full accent-emerald-400" aria-label="حد المعدل" />
                      <p className="text-[10px] text-zinc-600">الحد الأقصى المسموح 10 — التزم بحدود البرنامج (Allegro مثلًا: 5)</p>
                    </div>
                    <div className="grid grid-cols-3 gap-3">
                      <Field label="مهلة (ث)">
                        <Input type="number" min={3} max={60} className={INPUT_CLS} value={timeout_} onChange={(e) => setTimeout_(Number(e.target.value))} />
                      </Field>
                      <Field label="إعادات 429">
                        <Input type="number" min={0} max={5} className={INPUT_CLS} value={retries} onChange={(e) => setRetries(Number(e.target.value))} />
                      </Field>
                      <Field label="متغيرات/عملية">
                        <Input type="number" min={1} max={8} className={INPUT_CLS} value={maxVariants} onChange={(e) => setMaxVariants(Number(e.target.value))} />
                      </Field>
                    </div>
                    <div>
                      <div className="flex justify-between text-[12px] text-zinc-400 mb-1">
                        <span>بروبات السباق المتزامن (0 = معطل)</span>
                        <span className="font-mono text-rose-300">{race}</span>
                      </div>
                      <input type="range" min={0} max={8} step={1} value={race} onChange={(e) => setRace(Number(e.target.value))} className="w-full accent-rose-400" aria-label="بروبات السباق" />
                      <p className="text-[10px] text-zinc-600">درس OpenAI/redis: طلبات متزامنة بمعرفات عشوائية وتوكن المهاجم فقط — opt-in ومحدود بأول 5 نقاط</p>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[12px] text-zinc-300">وضع صارم (فشل حتى على مشتبه)</span>
                      <Switch checked={strict} onCheckedChange={setStrict} className="data-[state=checked]:bg-emerald-500" />
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[12px] text-zinc-300">تعطيل طلبات التحكم العشوائية</span>
                      <Switch checked={noControls} onCheckedChange={setNoControls} className="data-[state=checked]:bg-amber-500" />
                    </div>
                  </div>
                ) : null}
              </div>

              {/* Run */}
              <div className="flex gap-2">
                <Button
                  className="flex-1 h-11 bg-emerald-500 hover:bg-emerald-400 text-black font-bold"
                  disabled={!canRun}
                  onClick={runScan}
                >
                  <Play className="h-4 w-4" />
                  ابدأ المسح
                </Button>
                {running ? (
                  <Button variant="outline" className="h-11 border-red-500/40 text-red-300 hover:bg-red-500/10 hover:text-red-200" onClick={stopScan}>
                    <Square className="h-4 w-4" />
                    إيقاف
                  </Button>
                ) : null}
              </div>
              {!authorized ? (
                <p className="text-[11px] text-zinc-500 flex items-center gap-1.5">
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                  علّم إقرار التفويض أعلاه لتفعيل زر البدء
                </p>
              ) : null}
              {statusMsg ? <p className="text-[12px] text-emerald-300">{statusMsg}</p> : null}
              {running && progress ? (
                <div>
                  <div className="h-1.5 rounded bg-[#0a0f0d] overflow-hidden">
                    <div className="h-full bg-emerald-500 transition-all" style={{ width: `${Math.round((progress.i / Math.max(progress.n, 1)) * 100)}%` }} />
                  </div>
                  <p className="text-[10px] text-zinc-500 mt-1 font-mono" dir="ltr">
                    {progress.i}/{progress.n}
                  </p>
                </div>
              ) : null}
            </CardContent>
          </Card>

          {/* Results column */}
          <div className="space-y-6 min-w-0">
            <Card className={PANEL}>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Activity className="h-4 w-4 text-emerald-400" />
                  السجل الحي
                </CardTitle>
                <CardDescription className="text-zinc-500 text-[12px]">مخرجات محرك بايثون لحظة بلحظة</CardDescription>
              </CardHeader>
              <CardContent>
                <div ref={termRef} className="lm-scroll max-h-80 overflow-y-auto rounded-lg border border-[#1c2b25] bg-[#050807] p-3 font-mono text-[11.5px] leading-relaxed" dir="ltr">
                  {logs.length === 0 ? (
                    <p className="text-zinc-600">$ waiting for scan…</p>
                  ) : (
                    logs.map((l, i) => (
                      <p key={i} className={`whitespace-pre-wrap break-all ${l.includes("LEAK") ? "text-red-300" : l.includes("[stderr]") || l.includes("[fatal]") ? "text-orange-300" : l.startsWith("  [") ? "text-zinc-300" : "text-emerald-200/80"}`}>
                        {l}
                      </p>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>

            <Card className={PANEL}>
              <CardHeader className="flex-row items-start justify-between space-y-0">
                <div className="space-y-1.5">
                  <CardTitle className="text-base">نتائج المصفوفة</CardTitle>
                  <CardDescription className="text-zinc-500 text-[12px]">
                    {report ? `الإصدار ${report.version} — ${report.verdicts.length} نتيجة` : "شغّل مسحًا لعرض النتائج"}
                  </CardDescription>
                </div>
                {report ? (
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" className="border-[#1c2b25] text-zinc-300 hover:bg-emerald-500/10 hover:text-emerald-200" onClick={exportJson}>
                      <FileJson className="h-3.5 w-3.5" /> JSON
                    </Button>
                    <Button variant="outline" size="sm" className="border-[#1c2b25] text-zinc-300 hover:bg-emerald-500/10 hover:text-emerald-200" onClick={exportCsv}>
                      <FileSpreadsheet className="h-3.5 w-3.5" /> CSV
                    </Button>
                  </div>
                ) : null}
              </CardHeader>
              <CardContent className="space-y-4">
                {report ? (
                  <>
                    <div className={`rounded-lg border p-3 text-sm font-bold ${report.result === "FAIL" ? "border-red-500/50 bg-red-500/10 text-red-300" : "border-emerald-500/50 bg-emerald-500/10 text-emerald-300"}`}>
                      {report.result === "FAIL"
                        ? "FAIL — اكتُشفت تسريبات عبور مؤكدة. توثيق الأدلة فورًا وابلغ عبر البرنامج الرسمي فقط."
                        : "PASS — لا تسريبات مؤكدة في هذه المصفوفة. الحدود صمدت."}
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                      {ORDER.filter((k) => counts[k] > 0 || k === "LEAK" || k === "SUSPECT").map((k) => (
                        <StatCard key={k} k={k} count={counts[k]} />
                      ))}
                    </div>
                    <div className="lm-scroll max-h-96 overflow-y-auto rounded-lg border border-[#1c2b25]">
                      <table className="w-full text-[11.5px]">
                        <thead className="bg-[#0a100d] sticky top-0">
                          <tr className="text-zinc-400">
                            <th className="text-start px-3 py-2 font-medium">العملية</th>
                            <th className="text-start px-3 py-2 font-medium">التصنيف</th>
                            <th className="text-start px-3 py-2 font-medium">الحالة</th>
                            <th className="text-start px-3 py-2 font-medium">الدليل</th>
                          </tr>
                        </thead>
                        <tbody>
                          {report.verdicts.map((v, i) => {
                            const meta = VERDICT_META[v.klass] ?? VERDICT_META.OTHER;
                            return (
                              <tr key={i} className="border-t border-[#141f1a] hover:bg-[#0a100d]">
                                <td className="px-3 py-2 font-mono text-zinc-200 max-w-56" dir="ltr">
                                  <div className="truncate" title={v.url}>{v.operation}</div>
                                  <div className="truncate text-[10px] text-zinc-500" title={v.url}>{v.url}</div>
                                </td>
                                <td className="px-3 py-2">
                                  <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10.5px] whitespace-nowrap ${meta.chip}`}>
                                    <span className={`h-1.5 w-1.5 rounded-full ${meta.dot}`} />
                                    {meta.ar}
                                  </span>
                                  {v.secrets > 0 ? (
                                    <span className="block mt-1 text-[10px] text-rose-300 font-bold">أسرار: {v.secrets} [{v.secret_kinds}]</span>
                                  ) : null}
                                </td>
                                <td className="px-3 py-2 font-mono text-zinc-300">{v.status}</td>
                                <td className="px-3 py-2 text-zinc-500 text-[10.5px] max-w-40">
                                  <span className="block truncate" title={v.evidence ?? "body"}>{v.evidence ?? "body"}</span>
                                  <span className="text-zinc-600">{v.elapsed_ms}ms</span>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : (
                  <div className="rounded-lg border border-dashed border-[#1c2b25] p-8 text-center text-[12px] text-zinc-500 leading-relaxed">
                    لا توجد نتائج بعد.
                    <br />
                    جرّب زر «الهدف التجريبي الآمن» أعلى لوحة الإعداد لمشاهدة دورة كاملة: تسريب مؤكد + نقطة محمية + فخ إيجابية كاذبة يقتلها محرك التحكم التفريقي.
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>

      <footer className="mt-auto border-t border-[#1c2b25] bg-[#070b09]">
        <div className="mx-auto max-w-7xl px-4 py-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-[11px] text-zinc-500">
          <span>
            LeakMatrix Console — اختبار مصرّح به فقط. أي استخدام خارج التفويض مخالف لشروط الخدمة وقد يكون جنائيًا.
          </span>
          <a href="https://github.com/jsiadyarslan-lab/leakmatrix" target="_blank" rel="noreferrer" className="hover:text-emerald-300 transition-colors">
            github.com/jsiadyarslan-lab/leakmatrix
          </a>
        </div>
      </footer>
    </div>
  );
}

