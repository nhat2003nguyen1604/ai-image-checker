"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";

type Theme = "light" | "dark";

type AnalyzeResult = {
  scan_id?: string;
  label: string;
  confidence: number;
  reasons: string[];
  signals?: Record<string, any>;
  extra?: Record<string, any>;
};

type ScanItem = {
  scan_id?: string;
  filename: string;
  ts: number;
  label?: string;
  confidence?: number;
  cached?: AnalyzeResult;
};

type ChatMsg = {
  role: "user" | "bot";
  text: string;
  ts?: number;
};

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

const LS_SCANS = "ai_image_checker_recent_scans_v1";
const LS_CHAT = "ai_image_checker_chat_v1";
const LS_THEME = "ai_image_checker_theme_v1";

function niceLabel(label: string) {
  if (label === "likely_ai") return "Likely AI-generated";
  if (label === "likely_real") return "Likely Real";
  return "Unknown";
}

function pct(x: any) {
  if (typeof x !== "number" || Number.isNaN(x)) return "—";
  return `${(x * 100).toFixed(1)}%`;
}

function formatTime(ts: number) {
  try {
    return new Date(ts).toLocaleString();
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

function labelBadgeClass(label: string, isDark: boolean) {
  if (label === "likely_ai") {
    return isDark
      ? "bg-rose-500/15 text-rose-200 border-rose-400/30"
      : "bg-rose-50 text-rose-700 border-rose-200";
  }

  if (label === "likely_real") {
    return isDark
      ? "bg-emerald-500/15 text-emerald-200 border-emerald-400/30"
      : "bg-emerald-50 text-emerald-700 border-emerald-200";
  }

  return isDark
    ? "bg-amber-500/15 text-amber-200 border-amber-400/30"
    : "bg-amber-50 text-amber-700 border-amber-200";
}

export default function Page() {
  const [theme, setTheme] = useState<Theme>("light");
  const isDark = theme === "dark";

  const [file, setFile] = useState<File | null>(null);
  const [previewURL, setPreviewURL] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [showSignals, setShowSignals] = useState(false);
  const [reportCopied, setReportCopied] = useState(false);

  const [recent, setRecent] = useState<ScanItem[]>([]);

  const [vote, setVote] = useState<"correct" | "wrong" | null>(null);
  const [wrongNoteOpen, setWrongNoteOpen] = useState(false);
  const [wrongNote, setWrongNote] = useState("");
  const [fbBusy, setFbBusy] = useState(false);
  const [fbMsg, setFbMsg] = useState<string | null>(null);

  const [chatOpen, setChatOpen] = useState(false);
  const [chatBusy, setChatBusy] = useState(false);
  const [chatErr, setChatErr] = useState<string | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [chat, setChat] = useState<ChatMsg[]>([]);
  const chatListRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    try {
      const savedTheme = localStorage.getItem(LS_THEME);
      if (savedTheme === "dark" || savedTheme === "light") {
        setTheme(savedTheme);
      }
    } catch {}

    try {
      const raw = localStorage.getItem(LS_SCANS);
      if (raw) setRecent(JSON.parse(raw));
    } catch {}

    try {
      const raw = localStorage.getItem(LS_CHAT);
      if (raw) {
        setChat(JSON.parse(raw));
      } else {
        setChat([
          {
            role: "bot",
            text: "Hi! I can help you use this website: scanning, results, feedback, and troubleshooting.",
            ts: Date.now(),
          },
        ]);
      }
    } catch {
      setChat([
        {
          role: "bot",
          text: "Hi! I can help you use this website: scanning, results, feedback, and troubleshooting.",
          ts: Date.now(),
        },
      ]);
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(LS_THEME, theme);
    } catch {}
  }, [theme]);

  useEffect(() => {
    try {
      localStorage.setItem(LS_SCANS, JSON.stringify(recent.slice(0, 20)));
    } catch {}
  }, [recent]);

  useEffect(() => {
    try {
      localStorage.setItem(LS_CHAT, JSON.stringify(chat.slice(-50)));
    } catch {}
  }, [chat]);

  useEffect(() => {
    if (!chatOpen) return;
    const el = chatListRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [chatOpen, chat]);

  useEffect(() => {
    if (!file) {
      setPreviewURL(null);
      return;
    }

    const url = URL.createObjectURL(file);
    setPreviewURL(url);

    return () => URL.revokeObjectURL(url);
  }, [file]);

  const ui = {
    page: isDark
      ? "min-h-screen bg-slate-950 text-slate-100"
      : "min-h-screen bg-slate-50 text-slate-950",
    card: isDark
      ? "rounded-2xl border border-white/10 bg-slate-900 p-5 shadow-sm"
      : "rounded-2xl border border-slate-200 bg-white p-5 shadow-sm",
    subCard: isDark
      ? "rounded-2xl border border-white/10 bg-slate-950 p-4"
      : "rounded-2xl border border-slate-200 bg-slate-50 p-4",
    muted: isDark ? "text-slate-400" : "text-slate-600",
    primaryBtn: isDark
      ? "rounded-xl bg-white px-4 py-2 text-sm font-semibold text-slate-950 shadow hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-50"
      : "rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50",
    secondaryBtn: isDark
      ? "rounded-xl border border-white/10 bg-slate-800 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
      : "rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-slate-50",
    smallBtn: isDark
      ? "rounded-xl border border-white/10 bg-slate-800 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
      : "rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-950 hover:bg-slate-50 disabled:opacity-50",
    input: isDark
      ? "w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-white/30"
      : "w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-950 outline-none focus:ring-2 focus:ring-slate-300",
  };

  const canAnalyze = !!file && !busy;

  const signalsText = useMemo(() => {
    if (!result) return "";
    return safeJson({ signals: result.signals || {}, extra: result.extra || {} });
  }, [result]);

  function resetAll() {
    setFile(null);
    setPreviewURL(null);
    setResult(null);
    setErr(null);
    setShowSignals(false);
    setVote(null);
    setWrongNoteOpen(false);
    setWrongNote("");
    setFbMsg(null);
  }

  async function copyReportLink() {
  if (!result?.scan_id) return;

  const url = `${window.location.origin}/report/${result.scan_id}`;

  try {
    await navigator.clipboard.writeText(url);
    setReportCopied(true);
    setTimeout(() => setReportCopied(false), 1500);
  } catch {
    setReportCopied(false);
  }
}

  async function analyze() {
    if (!file) return;

    setBusy(true);
    setErr(null);
    setResult(null);
    setVote(null);
    setWrongNoteOpen(false);
    setWrongNote("");
    setFbMsg(null);

    try {
      const form = new FormData();
      form.append("file", file);

      const res = await fetch(`${BACKEND}/analyze`, {
        method: "POST",
        headers: API_KEY ? { "x-api-key": API_KEY } : undefined,
        body: form,
        cache: "no-store",
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const detail = data?.detail;
        throw new Error(typeof detail === "string" ? detail : `Analyze failed (${res.status})`);
      }

      const data = (await res.json()) as AnalyzeResult;
      setResult(data);

      setRecent((prev) => {
        const next: ScanItem[] = [
          {
            scan_id: data.scan_id,
            filename: file.name,
            ts: Date.now(),
            label: data.label,
            confidence: data.confidence,
            cached: data,
          },
          ...prev,
        ];

        const seen = new Set<string>();
        const dedup: ScanItem[] = [];

        for (const it of next) {
          const key = it.scan_id || `${it.filename}-${it.ts}`;
          if (seen.has(key)) continue;
          seen.add(key);
          dedup.push(it);
        }

        return dedup.slice(0, 20);
      });
    } catch (e: any) {
      setErr(e?.message || "Analyze failed");
    } finally {
      setBusy(false);
    }
  }

  async function sendFeedback(v: "correct" | "wrong", note?: string) {
    if (!result?.scan_id) return;

    setFbBusy(true);
    setFbMsg(null);

    try {
      const res = await fetch(`${BACKEND}/feedback`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(API_KEY ? { "x-api-key": API_KEY } : {}),
        },
        body: JSON.stringify({
          scan_id: result.scan_id,
          vote: v,
          note: note || "",
        }),
        cache: "no-store",
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const detail = data?.detail;
        throw new Error(typeof detail === "string" ? detail : `Feedback failed (${res.status})`);
      }

      setVote(v);
      setFbMsg(v === "wrong" ? "Thanks - your feedback was sent to admin." : "Thanks - marked as correct.");
    } catch (e: any) {
      setFbMsg(e?.message || "Failed to send feedback");
    } finally {
      setFbBusy(false);
    }
  }

  function onWrongClick() {
    setVote(null);
    setFbMsg(null);
    setWrongNoteOpen(true);
  }

  async function submitWrongNote() {
    const note = wrongNote.trim();

    if (!note) {
      setFbMsg("Please write a short note first.");
      return;
    }

    await sendFeedback("wrong", note);
    setWrongNoteOpen(false);
    setWrongNote("");
  }

  async function sendChat() {
    const text = chatInput.trim();
    if (!text) return;

    setChatErr(null);
    setChatBusy(true);
    setChatInput("");
    setChat((prev) => [...prev, { role: "user", text, ts: Date.now() }]);

    try {
      const res = await fetch(`${BACKEND}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(API_KEY ? { "x-api-key": API_KEY } : {}),
        },
        body: JSON.stringify({
          message: text,
          context: { last_result: result ?? null },
        }),
        cache: "no-store",
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        const detail = data?.detail;
        throw new Error(typeof detail === "string" ? detail : `Chat failed (${res.status})`);
      }

      const data = (await res.json()) as { reply: string };
      setChat((prev) => [...prev, { role: "bot", text: data.reply || "OK.", ts: Date.now() }]);
    } catch (e: any) {
      const msg = e?.message || "Chat failed";
      setChatErr(msg);
      setChat((prev) => [...prev, { role: "bot", text: `Sorry - chat failed. ${msg}`, ts: Date.now() }]);
    } finally {
      setChatBusy(false);
    }
  }

  function clearChat() {
    setChat([
      {
        role: "bot",
        text: "Hi! I can help you use this website: scanning, results, feedback, and troubleshooting.",
        ts: Date.now(),
      },
    ]);
    setChatErr(null);
  }

  return (
    <div className={ui.page}>
      <div className="mx-auto max-w-6xl px-4 py-8">
        <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className={`text-sm font-semibold ${ui.muted}`}>Explainable AI Image Detection</div>
            <h1 className="mt-1 text-4xl font-bold tracking-tight">AI Image Checker</h1>
            <p className={`mt-2 max-w-2xl text-sm ${ui.muted}`}>
              Upload an image and get a conservative result with confidence, reasons, forensic signals, feedback, and history.
            </p>
          </div>

          <button
            onClick={() => setTheme((v) => (v === "light" ? "dark" : "light"))}
            className={ui.secondaryBtn}
          >
            {isDark ? "Light mode" : "Dark mode"}
          </button>
        </header>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <section className={ui.card}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold">Upload image</h2>
                <p className={`mt-1 text-sm ${ui.muted}`}>JPEG, PNG, or WebP. Max 10MB.</p>
              </div>
              <span
                className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                  isDark ? "border-white/10 text-slate-300" : "border-slate-200 text-slate-600"
                }`}
              >
                Local demo
              </span>
            </div>

            <div
              className={`mt-5 rounded-2xl border border-dashed p-5 ${
                isDark ? "border-white/15 bg-slate-950" : "border-slate-300 bg-slate-50"
              }`}
            >
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className={`block w-full text-sm ${
                  isDark
                    ? "file:mr-4 file:rounded-lg file:border file:border-white/10 file:bg-slate-800 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-slate-700"
                    : "file:mr-4 file:rounded-lg file:border file:border-slate-300 file:bg-white file:px-4 file:py-2 file:text-sm file:font-semibold file:text-slate-950 hover:file:bg-slate-100"
                }`}
              />

              <div className="mt-4 flex flex-wrap gap-3">
                <button onClick={analyze} disabled={!canAnalyze} className={ui.primaryBtn}>
                  {busy ? "Analyzing..." : "Analyze"}
                </button>

                <button onClick={resetAll} className={ui.secondaryBtn}>
                  Reset
                </button>
              </div>
            </div>

            <div
              className={`mt-5 rounded-2xl border p-4 ${
                isDark ? "border-white/10 bg-slate-950" : "border-slate-200 bg-slate-50"
              }`}
            >
              <div className="text-sm font-bold">Preview</div>

              <div
                className={`mt-3 overflow-hidden rounded-xl border ${
                  isDark ? "border-white/10 bg-black" : "border-slate-200 bg-white"
                }`}
              >
                {previewURL ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={previewURL} alt="preview" className="h-[280px] w-full object-contain" />
                ) : (
                  <div className={`flex h-[180px] items-center justify-center text-sm ${ui.muted}`}>
                    No image selected.
                  </div>
                )}
              </div>
            </div>
          </section>

          <section className={ui.card}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold">Result report</h2>
                <p className={`mt-1 text-sm ${ui.muted}`}>Decision, confidence, and explanation.</p>
              </div>

              <button onClick={() => setShowSignals((v) => !v)} disabled={!result} className={ui.smallBtn}>
                {showSignals ? "Hide signals" : "View signals"}
              </button>
            </div>

            {!result && !err && (
              <div
                className={`mt-5 rounded-2xl border p-5 text-sm ${
                  isDark ? "border-white/10 bg-slate-950 text-slate-400" : "border-slate-200 bg-slate-50 text-slate-600"
                }`}
              >
                Upload an image and click Analyze.
              </div>
            )}

            {err && (
              <div className="mt-5 rounded-2xl border border-rose-300 bg-rose-50 p-4 text-sm text-rose-700">
                {err}
              </div>
            )}

            {result && (
              <div className="mt-5 space-y-4">
                <div className={ui.subCard}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full border px-3 py-1 text-xs font-bold ${labelBadgeClass(result.label, isDark)}`}>
                      {niceLabel(result.label)}
                    </span>
                    <span className={`text-xs ${ui.muted}`}>Scan ID: {result.scan_id || "—"}</span>
                  </div>
                  {result.scan_id && (
  <button
    onClick={copyReportLink}
    className={ui.smallBtn}
  >
    {reportCopied ? "Report link copied!" : "Copy report link"}
  </button>
)}

                  <div className="mt-4">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-semibold">Confidence</span>
                      <span className={ui.muted}>{pct(result.confidence)}</span>
                    </div>

                    <div className={`mt-2 h-3 overflow-hidden rounded-full ${isDark ? "bg-slate-800" : "bg-slate-200"}`}>
                      <div
                        className={isDark ? "h-full rounded-full bg-white transition-all" : "h-full rounded-full bg-slate-950 transition-all"}
                        style={{ width: `${Math.max(0, Math.min(100, (result.confidence || 0) * 100))}%` }}
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <div className="text-sm font-bold">Why this result</div>
                  <ul className={`mt-2 list-disc space-y-1 pl-5 text-sm ${isDark ? "text-slate-300" : "text-slate-700"}`}>
                    {result.reasons?.length ? result.reasons.map((r, idx) => <li key={idx}>{r}</li>) : <li>No reasons returned.</li>}
                  </ul>
                </div>

                {showSignals && (
                  <div className={ui.subCard}>
                    <div className="text-sm font-bold">Signals debug</div>
                    <pre
                      className={`mt-2 max-h-[260px] overflow-auto rounded-xl border p-3 text-xs ${
                        isDark ? "border-white/10 bg-black text-slate-300" : "border-slate-200 bg-white text-slate-800"
                      }`}
                    >
                      {signalsText || "{}"}
                    </pre>
                  </div>
                )}

                <div className={ui.subCard}>
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="text-sm font-bold">Feedback</div>

                    <button
                      onClick={() => {
                        setWrongNoteOpen(false);
                        setWrongNote("");
                        sendFeedback("correct");
                      }}
                      disabled={fbBusy || !result.scan_id}
                      className={`rounded-xl px-3 py-2 text-xs font-bold ${
                        vote === "correct"
                          ? "bg-emerald-600 text-white"
                          : isDark
                            ? "border border-white/10 bg-slate-800 text-white hover:bg-slate-700"
                            : "border border-slate-300 bg-white text-slate-950 hover:bg-slate-50"
                      }`}
                    >
                      Correct
                    </button>

                    <button
                      onClick={onWrongClick}
                      disabled={fbBusy || !result.scan_id}
                      className={`rounded-xl px-3 py-2 text-xs font-bold ${
                        vote === "wrong"
                          ? "bg-rose-600 text-white"
                          : isDark
                            ? "border border-white/10 bg-slate-800 text-white hover:bg-slate-700"
                            : "border border-slate-300 bg-white text-slate-950 hover:bg-slate-50"
                      }`}
                    >
                      Wrong
                    </button>

                    {fbBusy && <span className={`text-xs ${ui.muted}`}>Sending...</span>}
                  </div>

                  {fbMsg && <div className={`mt-2 text-sm ${ui.muted}`}>{fbMsg}</div>}

                  {wrongNoteOpen && (
                    <div
                      className={`mt-3 rounded-xl border p-3 ${
                        isDark ? "border-white/10 bg-slate-900" : "border-slate-200 bg-white"
                      }`}
                    >
                      <div className="text-sm font-bold">Tell us what went wrong</div>
                      <textarea
                        value={wrongNote}
                        onChange={(e) => setWrongNote(e.target.value)}
                        placeholder="Example: This is a real iPhone photo, but the model says AI."
                        className={`${ui.input} mt-2 min-h-[90px]`}
                      />

                      <div className="mt-2 flex gap-2">
                        <button onClick={submitWrongNote} disabled={fbBusy} className={ui.primaryBtn}>
                          Submit feedback
                        </button>

                        <button
                          onClick={() => {
                            setWrongNoteOpen(false);
                            setWrongNote("");
                          }}
                          className={ui.secondaryBtn}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </section>
        </div>

        <section className={`${ui.card} mt-6`}>
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold">Recent scans</h2>
              <p className={`mt-1 text-sm ${ui.muted}`}>Stored locally in this browser.</p>
            </div>

            <button onClick={() => setRecent([])} className={ui.smallBtn}>
              Clear
            </button>
          </div>

          {recent.length === 0 ? (
            <p className={`mt-4 text-sm ${ui.muted}`}>No recent scans yet.</p>
          ) : (
            <div className="mt-4 space-y-2">
              {recent.map((it, idx) => (
                <button
                  key={`${it.scan_id || it.ts}-${idx}`}
                  onClick={() => {
                    if (it.cached) {
                      setResult(it.cached);
                      setErr(null);
                      setVote(null);
                      setWrongNoteOpen(false);
                      setWrongNote("");
                      setFbMsg(null);
                    }
                  }}
                  className={`flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-3 text-left ${
                    isDark ? "border-white/10 bg-slate-950 hover:bg-slate-900" : "border-slate-200 bg-white hover:bg-slate-50"
                  }`}
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-bold">{it.filename}</div>
                    <div className={`text-xs ${ui.muted}`}>{formatTime(it.ts)}</div>
                  </div>

                  <div className={`shrink-0 text-xs ${ui.muted}`}>
                    {it.label ? `${niceLabel(it.label)} · ${pct(it.confidence)}` : "—"}
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>
      </div>

      <button
        onClick={() => setChatOpen((v) => !v)}
        className={
          isDark
            ? "fixed bottom-5 right-5 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-white text-slate-950 shadow-lg hover:bg-slate-200"
            : "fixed bottom-5 right-5 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-slate-950 text-white shadow-lg hover:bg-slate-800"
        }
        aria-label="Open chat"
        title="Chat"
      >
        AI
      </button>

      {chatOpen && (
        <div
          className={`fixed bottom-20 right-5 z-50 w-[360px] max-w-[92vw] overflow-hidden rounded-2xl border shadow-2xl ${
            isDark ? "border-white/10 bg-slate-950 text-white" : "border-slate-200 bg-white text-slate-950"
          }`}
        >
          <div className={`flex items-center justify-between border-b px-3 py-2 ${isDark ? "border-white/10" : "border-slate-200"}`}>
            <div className="text-sm font-bold">Support Chat</div>

            <div className="flex gap-2">
              <button onClick={clearChat} className={ui.smallBtn}>
                Clear
              </button>
              <button onClick={() => setChatOpen(false)} className={ui.smallBtn}>
                Close
              </button>
            </div>
          </div>

          <div ref={chatListRef} className="max-h-[340px] overflow-auto px-3 py-3">
            {chat.map((m, i) => (
              <div key={i} className={`mb-2 flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                    m.role === "user"
                      ? isDark
                        ? "bg-white text-slate-950"
                        : "bg-slate-950 text-white"
                      : isDark
                        ? "bg-slate-800 text-white"
                        : "bg-slate-100 text-slate-950"
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}
          </div>

          {chatErr && <div className="px-3 pb-2 text-xs text-rose-500">{chatErr}</div>}

          <div className={`flex items-center gap-2 border-t px-3 py-2 ${isDark ? "border-white/10" : "border-slate-200"}`}>
            <input
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") sendChat();
              }}
              placeholder={chatBusy ? "Sending..." : "Ask about scanning, results, errors..."}
              className={ui.input}
            />

            <button onClick={sendChat} disabled={chatBusy || !chatInput.trim()} className={ui.primaryBtn}>
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}