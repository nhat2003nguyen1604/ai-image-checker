"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

type ScanReport = {
  scan_id?: string;
  id?: string;
  ts?: number;
  filename?: string;
  label?: string;
  confidence?: number;
  reasons?: string[];
  signals?: Record<string, any>;
  extra?: Record<string, any>;
};

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";

function niceLabel(label?: string) {
  if (label === "likely_ai") return "Likely AI-generated";
  if (label === "likely_real") return "Likely Real";
  return "Unknown";
}

function pct(x: any) {
  if (typeof x !== "number" || Number.isNaN(x)) return "—";
  return `${(x * 100).toFixed(1)}%`;
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

function safeJson(obj: any) {
  try {
    return JSON.stringify(obj, null, 2);
  } catch {
    return String(obj);
  }
}

function labelClass(label?: string) {
  if (label === "likely_ai") {
    return "border-rose-200 bg-rose-50 text-rose-700";
  }

  if (label === "likely_real") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }

  return "border-amber-200 bg-amber-50 text-amber-700";
}

export default function ReportPage() {
  const params = useParams();
  const scanId = String(params?.scan_id || "");

  const [data, setData] = useState<ScanReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showSignals, setShowSignals] = useState(false);

  const reportId = data?.scan_id || data?.id || scanId;

  const signalsText = useMemo(() => {
    if (!data) return "";
    return safeJson({
      signals: data.signals || {},
      extra: data.extra || {},
    });
  }, [data]);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setErr(null);

      try {
        const res = await fetch(`${BACKEND}/scan/${encodeURIComponent(scanId)}`, {
          cache: "no-store",
        });

        if (!res.ok) {
          const json = await res.json().catch(() => null);
          throw new Error(json?.detail || `Report failed (${res.status})`);
        }

        const json = (await res.json()) as ScanReport;
        setData(json);
      } catch (e: any) {
        setErr(e?.message || "Failed to load report");
      } finally {
        setLoading(false);
      }
    }

    if (scanId) load();
  }, [scanId]);

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <div className="mx-auto max-w-4xl px-4 py-8">
        <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="text-sm font-semibold text-slate-600">Shared Scan Report</div>
            <h1 className="mt-1 text-4xl font-bold tracking-tight">AI Image Checker Report</h1>
            <p className="mt-2 text-sm text-slate-600">
              A shareable report showing the result, confidence, reasons, and technical signals.
            </p>
          </div>

          <button
            onClick={copyLink}
            className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800"
          >
            {copied ? "Copied!" : "Copy link"}
          </button>
        </header>

        {loading && (
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            Loading report...
          </div>
        )}

        {err && (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-700 shadow-sm">
            {err}
          </div>
        )}

        {data && !loading && !err && (
          <div className="space-y-6">
            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full border px-3 py-1 text-xs font-bold ${labelClass(data.label)}`}>
                  {niceLabel(data.label)}
                </span>

                <span className="text-xs text-slate-500">Scan ID: {reportId}</span>
              </div>

              <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-sm text-slate-600">Confidence</div>
                  <div className="mt-1 text-2xl font-bold">{pct(data.confidence)}</div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-sm text-slate-600">File</div>
                  <div className="mt-1 truncate text-sm font-semibold">{data.filename || "—"}</div>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-sm text-slate-600">Time</div>
                  <div className="mt-1 text-sm font-semibold">{fmtTime(data.ts)}</div>
                </div>
              </div>

              <div className="mt-5">
                <div className="mb-2 flex items-center justify-between text-sm">
                  <span className="font-semibold">Confidence bar</span>
                  <span className="text-slate-600">{pct(data.confidence)}</span>
                </div>

                <div className="h-3 overflow-hidden rounded-full bg-slate-200">
                  <div
                    className="h-full rounded-full bg-slate-950 transition-all"
                    style={{
                      width: `${Math.max(0, Math.min(100, (data.confidence || 0) * 100))}%`,
                    }}
                  />
                </div>
              </div>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-lg font-bold">Why this result</h2>

              <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-slate-700">
                {data.reasons?.length ? (
                  data.reasons.map((r, i) => <li key={i}>{r}</li>)
                ) : (
                  <li>No reasons were saved for this scan.</li>
                )}
              </ul>
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold">Technical signals</h2>

                <button
                  onClick={() => setShowSignals((v) => !v)}
                  className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-950 hover:bg-slate-50"
                >
                  {showSignals ? "Hide" : "Show"}
                </button>
              </div>

              {showSignals ? (
                <pre className="mt-3 max-h-[360px] overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-800">
                  {signalsText || "{}"}
                </pre>
              ) : (
                <p className="mt-3 text-sm text-slate-600">
                  Signals are hidden by default to keep the report easy to read.
                </p>
              )}
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
              This report is an indicator, not absolute proof. AI-image detection can be affected by compression,
              editing, missing metadata, screenshots, and social media re-uploading.
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
