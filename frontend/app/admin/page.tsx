"use client";

import React, { useEffect, useMemo, useState } from "react";

type Theme = "light" | "dark";

type FeedbackRow = {
  id?: string;
  ts?: number;
  scan_id?: string;
  vote?: "correct" | "wrong" | "up" | "down" | string;
  note?: string | null;
  comment?: string | null;
  label?: string;
  confidence?: number;
  expected_label?: string;
  expected?: string | null;
  status?: "new" | "reviewed" | "fixed" | string;
  reviewed_ts?: number;
};

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const ADMIN_TOKEN = process.env.NEXT_PUBLIC_ADMIN_TOKEN || "";
const LS_ADMIN_THEME = "ai_image_checker_admin_theme_v1";

function normalizeVote(v?: string) {
  if (v === "down") return "wrong";
  if (v === "up") return "correct";
  if (v === "wrong") return "wrong";
  if (v === "correct") return "correct";
  return v || "unknown";
}

function normalizeStatus(s?: string) {
  if (s === "reviewed") return "reviewed";
  if (s === "fixed") return "fixed";
  return "new";
}

function statusLabel(s?: string) {
  const status = normalizeStatus(s);
  if (status === "reviewed") return "Reviewed";
  if (status === "fixed") return "Fixed / Used";
  return "New";
}

function getNote(item: FeedbackRow) {
  const note = item.note ?? item.comment ?? "";
  return String(note || "").trim();
}

function fmtTime(ts?: number) {
  if (!ts) return "—";

  try {
    const n = Number(ts);
    const ms = n > 10_000_000_000 ? n : n * 1000;
    return new Date(ms).toLocaleString();
  } catch {
    return String(ts);
  }
}

function pct(x?: number) {
  if (typeof x !== "number" || Number.isNaN(x)) return "—";
  return `${(x * 100).toFixed(1)}%`;
}

function toCSV(rows: FeedbackRow[]) {
  const header = ["ts", "scan_id", "vote", "label", "confidence", "note"];

  const escape = (v: any) => {
    const s = String(v ?? "");
    if (s.includes('"') || s.includes(",") || s.includes("\n")) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };

  return [
    header.join(","),
    ...rows.map((r) =>
      [
        r.ts,
        r.scan_id,
        normalizeVote(r.vote),
        r.label || "",
        typeof r.confidence === "number" ? r.confidence : "",
        getNote(r),
      ]
        .map(escape)
        .join(",")
    ),
  ].join("\n");
}

export default function AdminPage() {
  const [theme, setTheme] = useState<Theme>("light");
  const isDark = theme === "dark";

  const [items, setItems] = useState<FeedbackRow[]>([]);
  const [loading, setLoading] = useState(false);

  // Important: default false, so admin sees BOTH correct and wrong
  const [onlyWrong, setOnlyWrong] = useState(false);

  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(200);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>("Never");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(LS_ADMIN_THEME);
      if (saved === "dark" || saved === "light") setTheme(saved);
    } catch {}
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(LS_ADMIN_THEME, theme);
    } catch {}
  }, [theme]);

  const ui = {
    page: isDark
      ? "min-h-screen bg-slate-950 text-slate-100"
      : "min-h-screen bg-slate-50 text-slate-950",

    card: isDark
      ? "rounded-2xl border border-white/10 bg-slate-900 p-5 shadow-sm"
      : "rounded-2xl border border-slate-200 bg-white p-5 shadow-sm",

    muted: isDark ? "text-slate-400" : "text-slate-600",

    input: isDark
      ? "rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-white/30"
      : "rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-950 outline-none focus:ring-2 focus:ring-slate-300",

    primaryBtn: isDark
      ? "rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-slate-200 disabled:opacity-50"
      : "rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50",

    secondaryBtn: isDark
      ? "rounded-xl border border-white/10 bg-slate-800 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
      : "rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-slate-50 disabled:opacity-50",
  };

  async function load(silent = false) {
    if (!silent) setLoading(true);
    setError(null);

    try {
      const url =
        `${BACKEND}/admin/feedback?limit=${encodeURIComponent(String(limit))}` +
        `&only_wrong=${onlyWrong ? 1 : 0}` +
        `&q=${encodeURIComponent(q)}`;

      const res = await fetch(url, {
        headers: { "x-admin-token": ADMIN_TOKEN },
        cache: "no-store",
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || `Admin fetch failed (${res.status})`);
      }

      const data = (await res.json()) as { items: FeedbackRow[] };
      setItems(data.items || []);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (e: any) {
      setError(e?.message || "Failed to load");
    } finally {
      if (!silent) setLoading(false);
    }
  }
    async function updateStatus(item: FeedbackRow, status: "new" | "reviewed" | "fixed") {
  try {
    const res = await fetch(`${BACKEND}/admin/feedback/status`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-admin-token": ADMIN_TOKEN,
      },
      body: JSON.stringify({
        id: item.id,
        scan_id: item.scan_id,
        ts: item.ts,
        status,
      }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => null);
      throw new Error(data?.detail || `Status update failed (${res.status})`);
    }

    await load(true);
  } catch (e: any) {
    setError(e?.message || "Failed to update status");
  }
}

  // Load once when page opens
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto refresh every 2 seconds
  useEffect(() => {
    const timer = setInterval(() => {
      load(true);
    }, 2000);

    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onlyWrong, q, limit]);

  const summary = useMemo(() => {
  const wrong = items.filter((x) => normalizeVote(x.vote) === "wrong").length;
  const correct = items.filter((x) => normalizeVote(x.vote) === "correct").length;
  const newItems = items.filter((x) => normalizeStatus(x.status) === "new").length;
  const reviewed = items.filter((x) => normalizeStatus(x.status) === "reviewed").length;
  const fixed = items.filter((x) => normalizeStatus(x.status) === "fixed").length;

  return {
    total: items.length,
    wrong,
    correct,
    wrongRate: items.length ? Math.round((wrong / items.length) * 100) : 0,
    newItems,
    reviewed,
    fixed,
  };
}, [items]);

  
  function exportCSV() {
    const csv = toCSV(items);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = "feedback.csv";
    a.click();

    URL.revokeObjectURL(url);
  }

  return (
    <div className={ui.page}>
      <div className="mx-auto max-w-6xl px-4 py-8">
        <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className={`text-sm font-semibold ${ui.muted}`}>Admin Dashboard</div>
            <h1 className="mt-1 text-4xl font-bold tracking-tight">Feedback Review</h1>
            <p className={`mt-2 text-sm ${ui.muted}`}>
              Auto-refreshes every 2 seconds. Shows Correct and Wrong by default.
            </p>
            <p className={`mt-1 text-xs ${ui.muted}`}>Last updated: {lastUpdated}</p>
          </div>

          <button
            onClick={() => setTheme((v) => (v === "light" ? "dark" : "light"))}
            className={ui.secondaryBtn}
          >
            {isDark ? "Light mode" : "Dark mode"}
          </button>
        </header>

        <section className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <div className={ui.card}>
            <div className={`text-sm ${ui.muted}`}>Total shown</div>
            <div className="mt-2 text-3xl font-bold">{summary.total}</div>
          </div>

          <div className={ui.card}>
            <div className={`text-sm ${ui.muted}`}>Wrong</div>
            <div className="mt-2 text-3xl font-bold text-rose-500">{summary.wrong}</div>
          </div>

          <div className={ui.card}>
            <div className={`text-sm ${ui.muted}`}>Correct</div>
            <div className="mt-2 text-3xl font-bold text-emerald-500">{summary.correct}</div>
          </div>

          <div className={ui.card}>
            <div className={`text-sm ${ui.muted}`}>Wrong rate</div>
            <div className="mt-2 text-3xl font-bold">{summary.wrongRate}%</div>
          </div>
        </section>

        <section className={`${ui.card} mt-6`}>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <label className={`flex items-center gap-2 text-sm ${ui.muted}`}>
                <input
                  type="checkbox"
                  checked={onlyWrong}
                  onChange={(e) => setOnlyWrong(e.target.checked)}
                />
                Show only wrong
              </label>

              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search scan ID or note..."
                className={`${ui.input} w-full sm:w-[260px]`}
              />

              <input
                type="number"
                min={1}
                max={2000}
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value || 200))}
                className={`${ui.input} w-full sm:w-[120px]`}
              />
            </div>

            <div className="flex gap-2">
              <button onClick={() => load()} disabled={loading} className={ui.primaryBtn}>
                {loading ? "Loading..." : "Refresh now"}
              </button>

              <button onClick={exportCSV} disabled={!items.length} className={ui.secondaryBtn}>
                Export CSV
              </button>
            </div>
          </div>

          {error && (
            <div className="mt-4 rounded-xl border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">
              {error}
            </div>
          )}
        </section>

        <section className="mt-6 space-y-3">
          {!items.length && !error && (
            <div className={ui.card}>
              <p className={`text-sm ${ui.muted}`}>No feedback yet.</p>
            </div>
          )}

          {items.map((item, idx) => {
            const vote = normalizeVote(item.vote);
            const note = getNote(item);

            return (
              <div key={item.id || `${item.scan_id}-${item.ts}-${idx}`} className={ui.card}>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={
                          vote === "wrong"
                            ? "rounded-full border border-rose-200 bg-rose-50 px-3 py-1 text-xs font-bold text-rose-700"
                            : vote === "correct"
                            ? "rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700"
                            : "rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-bold text-slate-700"
                        }
                      >
                        {vote}
                      </span>

                      <span className={`text-xs ${ui.muted}`}>
  Scan ID: {item.scan_id || "—"}
</span>

{item.scan_id && (
  <a
    href={`/report/${item.scan_id}`}
    target="_blank"
    rel="noreferrer"
    className={
      isDark
        ? "rounded-lg border border-sky-400/30 bg-sky-500/10 px-3 py-1 text-xs font-semibold text-sky-200 hover:bg-sky-500/20"
        : "rounded-lg border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 hover:bg-sky-100"
    }
  >
    Open report
  </a>
)}

                      {item.label && (
                        <span className={`text-xs ${ui.muted}`}>
                          Label: {item.label}
                        </span>
                      )}

                      {typeof item.confidence === "number" && (
                        <span className={`text-xs ${ui.muted}`}>
                          Confidence: {pct(item.confidence)}
                        </span>
                      )}
                    </div>

                    {note ? (
                      <p className="mt-3 whitespace-pre-wrap text-sm">{note}</p>
                    ) : (
                      <p className={`mt-3 text-sm ${ui.muted}`}>No note.</p>
                    )}
                  </div>

                  <div className={`text-xs ${ui.muted}`}>{fmtTime(item.ts)}</div>
                </div>
              </div>
            );
          })}
        </section>
      </div>
    </div>
  );
}