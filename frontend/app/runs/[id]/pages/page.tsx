"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

type Page = {
  id: string;
  run_id: string;
  url: string;
  title: string | null;
  greenwashing_score: number | null;
  created_at: string;
};

type Run = {
  id: string;
  name: string;
  status: string;
};

function ScoreCell({ score }: { score: number | null }) {
  if (score === null) return <span className="text-gray-400">—</span>;
  const color =
    score >= 0.7
      ? "text-red-600"
      : score >= 0.4
      ? "text-yellow-600"
      : "text-green-600";
  return <span className={`font-semibold ${color}`}>{score.toFixed(2)}</span>;
}

export default function PagesPage() {
  const { id: runId } = useParams<{ id: string }>();
  const supabase = createClient();

  const [run, setRun] = useState<Run | null>(null);
  const [pages, setPages] = useState<Page[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch run metadata
    supabase
      .from("crawl_runs")
      .select("id, name, status")
      .eq("id", runId)
      .single()
      .then(({ data }) => setRun(data));

    // Fetch pages for this run
    supabase
      .from("pages")
      .select("*")
      .eq("run_id", runId)
      .order("created_at", { ascending: false })
      .then(({ data }) => {
        setPages(data ?? []);
        setLoading(false);
      });

    // Realtime: crawl_runs status updates
    const runChannel = supabase
      .channel(`run-status-${runId}`)
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "crawl_runs",
          filter: `id=eq.${runId}`,
        },
        (payload) => {
          setRun((prev) =>
            prev ? { ...prev, ...(payload.new as Partial<Run>) } : prev
          );
        }
      )
      .subscribe();

    // Realtime: pages for this run (insert/update/delete)
    const pagesChannel = supabase
      .channel(`pages-${runId}`)
      .on(
        "postgres_changes",
        {
          event: "INSERT",
          schema: "public",
          table: "pages",
          filter: `run_id=eq.${runId}`,
        },
        (payload) => {
          setPages((prev) => [payload.new as Page, ...prev]);
        }
      )
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "pages",
          filter: `run_id=eq.${runId}`,
        },
        (payload) => {
          setPages((prev) =>
            prev.map((p) =>
              p.id === payload.new.id ? (payload.new as Page) : p
            )
          );
        }
      )
      .on(
        "postgres_changes",
        {
          event: "DELETE",
          schema: "public",
          table: "pages",
          filter: `run_id=eq.${runId}`,
        },
        (payload) => {
          setPages((prev) => prev.filter((p) => p.id !== payload.old.id));
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(runChannel);
      supabase.removeChannel(pagesChannel);
    };
  }, [runId]);

  const isRunning = run?.status === "running";

  return (
    <div className="min-h-screen">
      <header className="border-b border-gray-200 bg-white px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm">
          <Link href="/runs" className="text-gray-500 hover:text-gray-900">
            Runs
          </Link>
          <span className="text-gray-300">/</span>
          <span className="font-medium text-gray-900 truncate max-w-xs">
            {run?.name || runId}
          </span>
          {run && (
            <span
              className={`ml-1 inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                run.status === "running"
                  ? "bg-blue-100 text-blue-700"
                  : run.status === "completed"
                  ? "bg-green-100 text-green-700"
                  : run.status === "failed"
                  ? "bg-red-100 text-red-700"
                  : "bg-gray-100 text-gray-600"
              }`}
            >
              {run.status}
            </span>
          )}
        </div>

        <span className="flex items-center gap-1.5 text-xs text-gray-400">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-400 animate-pulse" />
          Live
        </span>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        <div className="mb-4 flex items-center gap-3">
          <h2 className="text-xl font-semibold text-gray-900">Crawled Pages</h2>
          <span className="text-sm text-gray-500">
            {pages.length} page{pages.length !== 1 ? "s" : ""}
            {isRunning && (
              <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse align-middle" />
            )}
          </span>
        </div>

        {loading ? (
          <p className="text-sm text-gray-500">Loading...</p>
        ) : pages.length === 0 ? (
          <p className="text-sm text-gray-500">
            {isRunning ? "Waiting for pages to be crawled…" : "No pages found for this run."}
          </p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <table className="min-w-full divide-y divide-gray-100">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-2/5">
                    URL
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-2/5">
                    Title
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Score
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Crawled
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {pages.map((page) => (
                  <tr key={page.id} className="hover:bg-gray-50">
                    <td className="px-5 py-3 text-sm text-blue-600 max-w-0 truncate">
                      <a
                        href={page.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={page.url}
                        className="block truncate"
                      >
                        {page.url}
                      </a>
                    </td>
                    <td className="px-5 py-3 text-sm text-gray-700 max-w-0 truncate">
                      <span className="block truncate" title={page.title ?? ""}>
                        {page.title ?? <span className="text-gray-400">—</span>}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-sm whitespace-nowrap">
                      <ScoreCell score={page.greenwashing_score} />
                    </td>
                    <td className="px-5 py-3 text-xs text-gray-400 whitespace-nowrap">
                      {new Date(page.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  );
}
