"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

type Run = {
  id: string;
  name: string;
  status: string;
  url: string;
  created_at: string;
};

const STATUS_STYLE: Record<string, string> = {
  running: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  pending: "bg-yellow-100 text-yellow-700",
};

export default function RunsPage() {
  const router = useRouter();
  const supabase = createClient();

  const [runs, setRuns] = useState<Run[]>([]);
  const [pageCounts, setPageCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  // Keep a stable ref so realtime callbacks always see current counts
  const pageCountsRef = useRef<Record<string, number>>({});
  pageCountsRef.current = pageCounts;

  useEffect(() => {
    // 1. Fetch initial runs
    supabase
      .from("crawl_runs")
      .select("*")
      .order("created_at", { ascending: false })
      .then(({ data }) => {
        setRuns(data ?? []);
        setLoading(false);
      });

    // 2. Fetch initial page counts grouped by run
    supabase
      .from("pages")
      .select("run_id")
      .then(({ data }) => {
        if (!data) return;
        const counts: Record<string, number> = {};
        for (const row of data) {
          counts[row.run_id] = (counts[row.run_id] ?? 0) + 1;
        }
        setPageCounts(counts);
      });

    // 3. Realtime: crawl_runs changes (status, name, etc.)
    const runsChannel = supabase
      .channel("crawl-runs-changes")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "crawl_runs" },
        (payload) => {
          if (payload.eventType === "INSERT") {
            setRuns((prev) => [payload.new as Run, ...prev]);
          } else if (payload.eventType === "UPDATE") {
            setRuns((prev) =>
              prev.map((r) =>
                r.id === payload.new.id ? (payload.new as Run) : r
              )
            );
          } else if (payload.eventType === "DELETE") {
            setRuns((prev) => prev.filter((r) => r.id !== payload.old.id));
          }
        }
      )
      .subscribe();

    // 4. Realtime: pages inserts/deletes → update per-run counts live
    const pagesChannel = supabase
      .channel("pages-count-changes")
      .on(
        "postgres_changes",
        { event: "INSERT", schema: "public", table: "pages" },
        (payload) => {
          const runId = payload.new.run_id as string;
          setPageCounts((prev) => ({
            ...prev,
            [runId]: (prev[runId] ?? 0) + 1,
          }));
        }
      )
      .on(
        "postgres_changes",
        { event: "DELETE", schema: "public", table: "pages" },
        (payload) => {
          const runId = payload.old.run_id as string;
          setPageCounts((prev) => ({
            ...prev,
            [runId]: Math.max(0, (prev[runId] ?? 1) - 1),
          }));
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(runsChannel);
      supabase.removeChannel(pagesChannel);
    };
  }, []);

  async function handleLogout() {
    await supabase.auth.signOut();
    router.push("/login");
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-gray-200 bg-white px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-900">Greenwashing Dashboard</h1>
        <button
          onClick={handleLogout}
          className="text-sm text-gray-500 hover:text-gray-900"
        >
          Sign out
        </button>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">Crawl Runs</h2>
          <span className="flex items-center gap-1.5 text-xs text-gray-400">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-400 animate-pulse" />
            Live
          </span>
        </div>

        {loading ? (
          <p className="text-sm text-gray-500">Loading...</p>
        ) : runs.length === 0 ? (
          <p className="text-sm text-gray-500">No runs yet.</p>
        ) : (
          <div className="space-y-2">
            {runs.map((run) => {
              const count = pageCounts[run.id] ?? 0;
              const isRunning = run.status === "running";
              return (
                <Link
                  key={run.id}
                  href={`/runs/${run.id}/pages`}
                  className="block rounded-lg border border-gray-200 bg-white px-5 py-4 hover:border-green-400 hover:shadow-sm transition-all"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <p className="font-medium text-gray-900 truncate">
                        {run.name || run.id}
                      </p>
                      <p className="mt-0.5 text-sm text-gray-500 truncate">{run.url}</p>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      {/* Live page count */}
                      <span className="text-sm text-gray-500">
                        {count} page{count !== 1 ? "s" : ""}
                        {isRunning && (
                          <span className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse align-middle" />
                        )}
                      </span>

                      {/* Status badge */}
                      <span
                        className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          STATUS_STYLE[run.status] ?? "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {run.status}
                      </span>

                      <span className="text-xs text-gray-400 whitespace-nowrap">
                        {new Date(run.created_at).toLocaleString()}
                      </span>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
