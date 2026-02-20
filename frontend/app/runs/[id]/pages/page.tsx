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

export default function PagesPage() {
  const { id: runId } = useParams<{ id: string }>();
  const supabase = createClient();
  const [pages, setPages] = useState<Page[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Initial fetch
    supabase
      .from("pages")
      .select("*")
      .eq("run_id", runId)
      .order("created_at", { ascending: false })
      .then(({ data }) => {
        setPages(data ?? []);
        setLoading(false);
      });

    // Realtime subscription scoped to this run
    const channel = supabase
      .channel(`pages-${runId}`)
      .on(
        "postgres_changes",
        {
          event: "*",
          schema: "public",
          table: "pages",
          filter: `run_id=eq.${runId}`,
        },
        (payload) => {
          if (payload.eventType === "INSERT") {
            setPages((prev) => [payload.new as Page, ...prev]);
          } else if (payload.eventType === "UPDATE") {
            setPages((prev) =>
              prev.map((p) => (p.id === payload.new.id ? (payload.new as Page) : p))
            );
          } else if (payload.eventType === "DELETE") {
            setPages((prev) => prev.filter((p) => p.id !== payload.old.id));
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [runId]);

  function scoreColor(score: number | null) {
    if (score === null) return "text-gray-400";
    if (score >= 0.7) return "text-red-600 font-semibold";
    if (score >= 0.4) return "text-yellow-600 font-semibold";
    return "text-green-600 font-semibold";
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-gray-200 bg-white px-6 py-4 flex items-center gap-3">
        <Link href="/runs" className="text-sm text-gray-500 hover:text-gray-900">
          Runs
        </Link>
        <span className="text-gray-300">/</span>
        <span className="text-sm font-medium text-gray-900 truncate max-w-xs">{runId}</span>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-gray-900">Crawled Pages</h2>
          <span className="text-xs text-gray-400">Live updates enabled</span>
        </div>

        {loading ? (
          <p className="text-sm text-gray-500">Loading...</p>
        ) : pages.length === 0 ? (
          <p className="text-sm text-gray-500">No pages found for this run.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <table className="min-w-full divide-y divide-gray-100">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    URL
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
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
                    <td className="px-5 py-3 text-sm text-blue-600 max-w-xs truncate">
                      <a href={page.url} target="_blank" rel="noopener noreferrer" title={page.url}>
                        {page.url}
                      </a>
                    </td>
                    <td className="px-5 py-3 text-sm text-gray-700 max-w-xs truncate">
                      {page.title ?? <span className="text-gray-400">—</span>}
                    </td>
                    <td className={`px-5 py-3 text-sm ${scoreColor(page.greenwashing_score)}`}>
                      {page.greenwashing_score !== null
                        ? page.greenwashing_score.toFixed(2)
                        : <span className="text-gray-400">—</span>}
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
