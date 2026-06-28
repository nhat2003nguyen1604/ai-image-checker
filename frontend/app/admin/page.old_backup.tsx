"use client";

import { useEffect, useState } from "react";

type FeedbackRow = {
  ts?: string;
  scan_id?: string;
  vote?: string;
  note?: string;
};

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8000";
const ADMIN_TOKEN = process.env.NEXT_PUBLIC_ADMIN_TOKEN || "";

export default function AdminPage() {
  const [items, setItems] = useState<FeedbackRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const res = await fetch(`${BACKEND}/admin/feedback`, {
        headers: { "x-admin-token": ADMIN_TOKEN },
        cache: "no-store",
      });
      if (!res.ok) throw new Error("Unauthorized or failed");
      const data = await res.json();
      setItems(data.items || []);
    } catch (e: any) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-white p-8">
      <h1 className="text-2xl font-bold mb-4">Admin – Feedback</h1>

      {error && <p className="text-red-400">{error}</p>}

      {items.map((f, i) => (
        <div key={i} className="border border-white/10 p-3 mb-2 rounded">
          <div className="text-sm text-slate-400">{f.ts}</div>
          <div>Scan: {f.scan_id}</div>
          <div>Vote: {f.vote}</div>
          {f.note && <div>Note: {f.note}</div>}
        </div>
      ))}
    </div>
  );
}
