"use client";

import { useEffect, useState } from "react";
import { env } from "@/lib/env";

interface HealthPayload {
  status: string;
  service: string;
  environment: string;
  database: string;
}

type ConnectionState =
  | { state: "loading" }
  | { state: "online"; payload: HealthPayload }
  | { state: "offline"; reason: string };

export function SystemHealthBadge() {
  const [health, setHealth] = useState<ConnectionState>({ state: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    const backendOrigin = env.apiBaseUrl.replace(/\/api\/v1\/?$/, "");

    fetch(`${backendOrigin}/health`, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = (await res.json()) as HealthPayload;
        setHealth({ state: "online", payload: data });
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setHealth({
          state: "offline",
          reason: err instanceof Error ? err.message : "Backend unreachable",
        });
      });

    return () => controller.abort();
  }, []);

  if (health.state === "loading") {
    return (
      <div className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-xs text-slate-600">
        <span className="h-2 w-2 animate-pulse rounded-full bg-amber-400" />
        Checking backend &amp; PostgreSQL connectivity...
      </div>
    );
  }

  if (health.state === "offline") {
    return (
      <div className="inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2 text-xs text-rose-700">
        <span className="h-2 w-2 rounded-full bg-rose-500" />
        Backend offline ({health.reason})
      </div>
    );
  }

  const dbConnected = health.payload.database === "connected";

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="inline-flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-800">
        <span className="h-2 w-2 rounded-full bg-emerald-500" />
        Backend API: Connected
      </div>
      <div
        className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium ${
          dbConnected
            ? "border-emerald-200 bg-emerald-50 text-emerald-800"
            : "border-amber-200 bg-amber-50 text-amber-800"
        }`}
      >
        <span
          className={`h-2 w-2 rounded-full ${dbConnected ? "bg-emerald-500" : "bg-amber-500"}`}
        />
        PostgreSQL: {dbConnected ? "Connected" : "Disconnected"}
      </div>
    </div>
  );
}

