"use client";

import React, { useMemo, useState } from "react";

type ApiResult = {
  label: "likely_ai" | "likely_real" | "unknown" | string;
  confidence: number; // 0..1
  signals: Record<string, any>;
  extra?: Record<string, any>;
  reasons?: string[];
};

type ChatMsg = { role: "user" | "assistant"; content: string };

function clamp01(x: number) {
  if (Number.isNaN(x)) return 0;
  return Math.max(0, Math.min(1, x));
}

function labelBadge(label: string) {
  const base: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "6px 10px",
    borderRadius: 999,
    fontWeight: 800,
    fontSize: 12,
    letterSpacing: 0.2,
    border: "1px solid rgba(0,0,0,0.10)",
  };

  if (label === "likely_ai") return { ...base, background: "rgba(255, 77, 79, 0.12)" };
  if (label === "likely_real") return { ...base, background: "rgba(82, 196, 26, 0.12)" };
  return { ...base, background: "rgba(250, 173, 20, 0.12)" };
}

function labelText(label: string) {
  if (label === "likely_ai") return "Likely AI-generated / AI-edited";
  if (label === "likely_real") return "Likely Real (camera-origin)";
  return "Uncertain";
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ApiResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Chat states
  const [chatOpen, setChatOpen] = useState(true);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatMsgs, setChatMsgs] = useState<ChatMsg[]>([
    {
      role: "assistant",
      content:
        'Hi! Ask me about "unknown" results, confidence, EXIF, or how the detector works.',
    },
  ]);

  const previewUrl = useMemo(() => {
    if (!file) return null;
    return URL.createObjectURL(file);
  }, [file]);

  async function analyze() {
    if (!file) return;

    setLoading(true);
    setErr(null);
    setResult(null);

    try {
      const form = new FormData();
      form.append("file", file);

      const r = await fetch("http://127.0.0.1:8000/analyze", {
        method: "POST",
        headers: { "x-api-key": "dev_secret_123" },
        body: form,
      });

      if (!r.ok) {
        const t = await r.text();
        throw new Error(t || "Request failed");
      }

      const data = (await r.json()) as ApiResult;
      data.confidence = clamp01(data.confidence);
      setResult(data);

      // Optional: after analyzing, add a helpful assistant message
      setChatMsgs((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            'Analysis complete. You can ask: "Why did it output this label?" or "What does EXIF mean?"',
        },
      ]);
    } catch (e: any) {
      setErr(e?.message || "Request failed");
    } finally {
      setLoading(false);
    }
  }

  async function sendChat() {
    const text = chatInput.trim();
    if (!text || chatLoading) return;

    const next: ChatMsg[] = [...chatMsgs, { role: "user", content: text }];
    setChatMsgs(next);
    setChatInput("");
    setChatLoading(true);

    try {
      const r = await fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-api-key": "dev_secret_123" },
        body: JSON.stringify({ messages: next }),
      });

      if (!r.ok) {
        const t = await r.text();
        throw new Error(t || "Chat request failed");
      }

      const data = await r.json();
      setChatMsgs([...next, { role: "assistant", content: data.reply }]);
    } catch (e: any) {
      setChatMsgs([
        ...next,
        { role: "assistant", content: "Chat error: " + (e?.message || "failed") },
      ]);
    } finally {
      setChatLoading(false);
    }
  }

  const confPct = result ? Math.round(clamp01(result.confidence) * 1000) / 10 : 0;

  return (
    <main
      style={{
        minHeight: "100vh",
        background:
          "radial-gradient(1200px 600px at 10% 10%, rgba(24,144,255,0.10), transparent 60%), radial-gradient(900px 500px at 90% 20%, rgba(82,196,26,0.10), transparent 55%), #ffffff",
        padding: 24,
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, Arial, sans-serif',
        color: "#111827",
      }}
    >
      <div style={{ maxWidth: 980, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ marginBottom: 18 }}>
          <div
            style={{
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "space-between",
              gap: 16,
              flexWrap: "wrap",
            }}
          >
            <div>
              <h1 style={{ margin: 0, fontSize: 28, letterSpacing: -0.4 }}>
                AI Image Authenticity Checker
              </h1>
              <p style={{ marginTop: 8, marginBottom: 0, color: "#4B5563" }}>
                Upload an image to estimate whether it looks AI-generated or edited,
                and review forensic signals.
              </p>
            </div>

            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 10,
                padding: "10px 12px",
                borderRadius: 14,
                border: "1px solid rgba(0,0,0,0.08)",
                background: "rgba(255,255,255,0.75)",
                backdropFilter: "blur(6px)",
              }}
            >
              <span style={{ fontSize: 12, color: "#6B7280" }}>Backend:</span>
              <span
                style={{
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                  fontSize: 12,
                }}
              >
                http://127.0.0.1:8000
              </span>
            </div>
          </div>
        </div>

        {/* Layout */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 16,
          }}
        >
          {/* Left: Upload + Preview */}
          <section
            style={{
              border: "1px solid rgba(0,0,0,0.08)",
              borderRadius: 18,
              padding: 16,
              background: "rgba(255,255,255,0.85)",
              boxShadow: "0 8px 22px rgba(17,24,39,0.06)",
            }}
          >
            <h2 style={{ margin: 0, fontSize: 16 }}>Upload</h2>
            <p style={{ marginTop: 8, color: "#6B7280", fontSize: 13 }}>
              Supported: JPG/PNG/WebP. Best results with original files (not heavily compressed).
            </p>

            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <label
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "10px 12px",
                  borderRadius: 14,
                  border: "1px solid rgba(0,0,0,0.10)",
                  background: "white",
                  cursor: "pointer",
                }}
              >
                <span style={{ fontWeight: 800, fontSize: 13 }}>Choose file</span>
                <input
                  type="file"
                  accept="image/*"
                  style={{ display: "none" }}
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
              </label>

              <button
                onClick={analyze}
                disabled={!file || loading}
                style={{
                  padding: "10px 14px",
                  borderRadius: 14,
                  border: "1px solid rgba(0,0,0,0.10)",
                  background: !file || loading ? "#F3F4F6" : "#111827",
                  color: !file || loading ? "#6B7280" : "white",
                  fontWeight: 900,
                  fontSize: 13,
                  cursor: !file || loading ? "not-allowed" : "pointer",
                }}
              >
                {loading ? "Analyzing…" : "Analyze"}
              </button>

              {file && (
                <button
                  onClick={() => {
                    setFile(null);
                    setResult(null);
                    setErr(null);
                  }}
                  disabled={loading}
                  style={{
                    padding: "10px 14px",
                    borderRadius: 14,
                    border: "1px solid rgba(0,0,0,0.10)",
                    background: "white",
                    fontWeight: 800,
                    fontSize: 13,
                    cursor: loading ? "not-allowed" : "pointer",
                  }}
                >
                  Reset
                </button>
              )}
            </div>

            <div style={{ marginTop: 14 }}>
              <div
                style={{
                  borderRadius: 16,
                  border: "1px dashed rgba(0,0,0,0.18)",
                  background: "rgba(249,250,251,0.9)",
                  padding: 12,
                  minHeight: 280,
                  display: "grid",
                  placeItems: "center",
                  overflow: "hidden",
                }}
              >
                {!previewUrl ? (
                  <div style={{ textAlign: "center", color: "#6B7280" }}>
                    <div style={{ fontSize: 40, marginBottom: 8 }}>🖼️</div>
                    <div style={{ fontWeight: 800 }}>No image selected</div>
                    <div style={{ fontSize: 13, marginTop: 6 }}>
                      Choose a file to preview it here.
                    </div>
                  </div>
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={previewUrl}
                    alt="Preview"
                    style={{
                      width: "100%",
                      height: 320,
                      objectFit: "contain",
                      borderRadius: 12,
                      background: "white",
                    }}
                  />
                )}
              </div>

              {file && (
                <div style={{ marginTop: 10, color: "#6B7280", fontSize: 12 }}>
                  <b style={{ color: "#111827" }}>Selected:</b> {file.name} •{" "}
                  {Math.round(file.size / 1024)} KB
                </div>
              )}
            </div>

            {err && (
              <div
                style={{
                  marginTop: 14,
                  padding: 12,
                  borderRadius: 14,
                  border: "1px solid rgba(255,77,79,0.25)",
                  background: "rgba(255,77,79,0.08)",
                  color: "#B91C1C",
                  fontSize: 13,
                }}
              >
                <b>Error:</b> {err}
              </div>
            )}
          </section>

          {/* Right: Result + Chat */}
          <section
            style={{
              border: "1px solid rgba(0,0,0,0.08)",
              borderRadius: 18,
              padding: 16,
              background: "rgba(255,255,255,0.85)",
              boxShadow: "0 8px 22px rgba(17,24,39,0.06)",
            }}
          >
            <h2 style={{ margin: 0, fontSize: 16 }}>Result</h2>
            <p style={{ marginTop: 8, color: "#6B7280", fontSize: 13 }}>
              This is an estimate. Use it as a signal, not definitive proof.
            </p>

            {!result ? (
              <div
                style={{
                  marginTop: 12,
                  borderRadius: 16,
                  border: "1px solid rgba(0,0,0,0.08)",
                  background: "rgba(249,250,251,0.9)",
                  padding: 16,
                  minHeight: 170,
                  display: "grid",
                  placeItems: "center",
                  color: "#6B7280",
                  textAlign: "center",
                }}
              >
                <div>
                  <div style={{ fontSize: 40, marginBottom: 8 }}>🔎</div>
                  <div style={{ fontWeight: 800 }}>No analysis yet</div>
                  <div style={{ fontSize: 13, marginTop: 6 }}>
                    Upload an image and click Analyze to see results.
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                  <span style={labelBadge(result.label)}>{labelText(result.label)}</span>
                  <span style={{ color: "#6B7280", fontSize: 13 }}>
                    Confidence: <b style={{ color: "#111827" }}>{confPct}%</b>
                  </span>
                </div>

                {/* Confidence bar */}
                <div style={{ marginTop: 12 }}>
                  <div
                    style={{
                      height: 10,
                      borderRadius: 999,
                      background: "rgba(0,0,0,0.06)",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${clamp01(result.confidence) * 100}%`,
                        height: "100%",
                        background: "rgba(17,24,39,0.85)",
                      }}
                    />
                  </div>
                  <div style={{ marginTop: 8, fontSize: 12, color: "#6B7280" }}>
                    Confidence increases as the prediction moves further from the uncertain zone.
                  </div>
                </div>

                {/* Explain Why */}
                {result.reasons && result.reasons.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontWeight: 900, fontSize: 13, marginBottom: 8 }}>
                      Why this result
                    </div>
                    <ul
                      style={{
                        margin: 0,
                        paddingLeft: 18,
                        color: "#374151",
                        fontSize: 13,
                        lineHeight: 1.45,
                      }}
                    >
                      {result.reasons.map((r, i) => (
                        <li key={i} style={{ marginBottom: 6 }}>
                          {r}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Details */}
                <div style={{ marginTop: 14 }}>
                  <details
                    style={{
                      border: "1px solid rgba(0,0,0,0.08)",
                      borderRadius: 14,
                      padding: 12,
                      background: "rgba(249,250,251,0.9)",
                    }}
                  >
                    <summary style={{ cursor: "pointer", fontWeight: 900, fontSize: 13 }}>
                      Show forensic signals
                    </summary>
                    <pre
                      style={{
                        marginTop: 10,
                        fontSize: 12,
                        overflowX: "auto",
                        padding: 10,
                        borderRadius: 12,
                        background: "white",
                        border: "1px solid rgba(0,0,0,0.08)",
                      }}
                    >
                      {JSON.stringify(result.signals, null, 2)}
                    </pre>
                  </details>

                  {result.extra && (
                    <details
                      style={{
                        marginTop: 10,
                        border: "1px solid rgba(0,0,0,0.08)",
                        borderRadius: 14,
                        padding: 12,
                        background: "rgba(249,250,251,0.9)",
                      }}
                    >
                      <summary style={{ cursor: "pointer", fontWeight: 900, fontSize: 13 }}>
                        Show model debug (optional)
                      </summary>
                      <pre
                        style={{
                          marginTop: 10,
                          fontSize: 12,
                          overflowX: "auto",
                          padding: 10,
                          borderRadius: 12,
                          background: "white",
                          border: "1px solid rgba(0,0,0,0.08)",
                        }}
                      >
                        {JSON.stringify(result.extra, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </>
            )}

            {/* Chatbot panel */}
            <div style={{ marginTop: 14 }}>
              <div
                style={{
                  border: "1px solid rgba(0,0,0,0.08)",
                  borderRadius: 14,
                  background: "rgba(249,250,251,0.9)",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "10px 12px",
                    background: "rgba(255,255,255,0.9)",
                    borderBottom: "1px solid rgba(0,0,0,0.06)",
                  }}
                >
                  <div style={{ fontWeight: 900, fontSize: 13 }}>Assistant</div>
                  <button
                    onClick={() => setChatOpen(!chatOpen)}
                    style={{
                      padding: "6px 10px",
                      borderRadius: 12,
                      border: "1px solid rgba(0,0,0,0.10)",
                      background: "white",
                      fontWeight: 800,
                      fontSize: 12,
                      cursor: "pointer",
                    }}
                  >
                    {chatOpen ? "Hide" : "Show"}
                  </button>
                </div>

                {chatOpen && (
                  <>
                    <div
                      style={{
                        maxHeight: 220,
                        overflowY: "auto",
                        padding: 12,
                        display: "flex",
                        flexDirection: "column",
                        gap: 10,
                      }}
                    >
                      {chatMsgs.map((m, i) => (
                        <div
                          key={i}
                          style={{
                            alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                            background: m.role === "user" ? "rgba(17,24,39,0.08)" : "white",
                            border: "1px solid rgba(0,0,0,0.08)",
                            borderRadius: 14,
                            padding: "10px 12px",
                            maxWidth: "85%",
                            fontSize: 13,
                            lineHeight: 1.35,
                          }}
                        >
                          {m.content}
                        </div>
                      ))}
                      {chatLoading && (
                        <div style={{ color: "#6B7280", fontSize: 12 }}>Thinking…</div>
                      )}
                    </div>

                    <div
                      style={{
                        display: "flex",
                        gap: 10,
                        padding: 12,
                        borderTop: "1px solid rgba(0,0,0,0.06)",
                        background: "rgba(255,255,255,0.9)",
                      }}
                    >
                      <input
                        value={chatInput}
                        onChange={(e) => setChatInput(e.target.value)}
                        placeholder='Try: "Why is it unknown?"'
                        onKeyDown={(e) => {
                          if (e.key === "Enter") sendChat();
                        }}
                        style={{
                          flex: 1,
                          padding: "10px 12px",
                          borderRadius: 14,
                          border: "1px solid rgba(0,0,0,0.10)",
                          outline: "none",
                          fontSize: 13,
                          background: "white",
                        }}
                      />
                      <button
                        onClick={sendChat}
                        disabled={chatLoading || !chatInput.trim()}
                        style={{
                          padding: "10px 14px",
                          borderRadius: 14,
                          border: "1px solid rgba(0,0,0,0.10)",
                          background: chatLoading || !chatInput.trim() ? "#F3F4F6" : "#111827",
                          color: chatLoading || !chatInput.trim() ? "#6B7280" : "white",
                          fontWeight: 900,
                          fontSize: 13,
                          cursor: chatLoading || !chatInput.trim() ? "not-allowed" : "pointer",
                        }}
                      >
                        Send
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </section>
        </div>

        <footer style={{ marginTop: 18, color: "#6B7280", fontSize: 12 }}>
          Tip: Social media images often remove EXIF metadata, so results can be less certain.
        </footer>
      </div>
    </main>
  );
}
