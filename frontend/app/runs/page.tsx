"use client";

import { useEffect, useState } from "react";
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

export default function RunsPage() {
  const router = useRouter();
  const supabase = createClient();
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Initial fetch
    supabase
      .from("runs")
      .select("*")
      .order("created_at", { ascending: false })
      .then(({ data }) => {
        setRuns(data ?? []);
        setLoading(false);
      });

    // Realtime subscription
    const channel = supabase
      .channel("runs-changes")
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "runs" },
        (payload) => {
          if (payload.eventType === "INSERT") {
            setRuns((prev) => [payload.new as Run, ...prev]);
          } else if (payload.eventType === "UPDATE") {
            setRuns((prev) =>
              prev.map((r) => (r.id === payload.new.id ? (payload.new as Run) : r))
            );
          } else if (payload.eventType === "DELETE") {
            setRuns((prev) => prev.filter((r) => r.id !== payload.old.id));
          }
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  async function handleLogout() {
    await supabase.auth.signOut();
    router.push("/login");
  }

  const statusColor: Record<string, string> = {
    running: "bg-blue-100 text-blue-700",
    completed: "bg-green-100 text-green-700",
    failed: "bg-red-100 text-red-700",
    pending: "bg-yellow-100 text-yellow-700",
  };

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
          <span className="text-xs text-gray-400">Live updates enabled</span>
        </div>

        {loading ? (
          <p className="text-sm text-gray-500">Loading...</p>
        ) : runs.length === 0 ? (
          <p className="text-sm text-gray-500">No runs yet.</p>
        ) : (
          <div className="space-y-2">
            {runs.map((run) => (
              <Link
                key={run.id}
                href={`/runs/${run.id}/pages`}
                className="block rounded-lg border border-gray-200 bg-white px-5 py-4 hover:border-green-400 hover:shadow-sm transition-all"
              >
                <div className="flex items-center justify-between">
                  <div className="min-w-0">
                    <p className="font-medium text-gray-900 truncate">{run.name || run.id}</p>
                    <p className="mt-0.5 text-sm text-gray-500 truncate">{run.url}</p>
                  </div>
                  <div className="ml-4 flex items-center gap-3 shrink-0">
                    <span
                      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        statusColor[run.status] ?? "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {run.status}
                    </span>
                    <span className="text-xs text-gray-400">
                      {new Date(run.created_at).toLocaleString()}
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
