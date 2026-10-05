import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Info } from "lucide-react";
import { motion } from "motion/react";
import { toast } from "sonner";

import { Logo } from "@/components/brand/Logo";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { api, type AccountStatus, type SyncRun } from "@/lib/api";
import { cn } from "@/lib/utils";

type ConnectionStatus = "connected" | "error" | "needs_auth" | "disconnected";

type SyncSourceDetail = {
  status?: string;
  mode?: string;
  posts?: number;
  comments?: number;
  releases?: number;
  reason?: string;
  error?: string;
};

function asConnectionStatus(status: string): ConnectionStatus | string {
  if (
    status === "connected" ||
    status === "error" ||
    status === "needs_auth" ||
    status === "disconnected"
  ) {
    return status;
  }
  return status;
}

function statusBadge(status: string): { label: string; className: string } {
  const normalized = asConnectionStatus(status);
  switch (normalized) {
    case "connected":
      return {
        label: "Connected",
        className:
          "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/25",
      };
    case "error":
      return {
        label: "Error",
        className: "bg-destructive/10 text-destructive border-destructive/25",
      };
    case "needs_auth":
      return {
        label: "No auth",
        className:
          "bg-amber-500/10 text-amber-800 dark:text-amber-400 border-amber-500/25",
      };
    case "disconnected":
      return {
        label: "Disconnected",
        className: "bg-muted text-muted-foreground border-border",
      };
    default: {
      const _exhaustive: string = normalized;
      return {
        label: _exhaustive,
        className: "bg-muted text-muted-foreground border-border",
      };
    }
  }
}

function formatSyncedAt(value?: string | null): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function accountSubtitle(account: AccountStatus): string {
  return account.display_name || account.username || account.external_id || "";
}

function SyncDetails({ run }: { run: SyncRun }) {
  const entries = Object.entries(run.per_source ?? {});
  return (
    <div className="rounded-md border border-border bg-muted/40 px-3 py-3 text-xs text-muted-foreground">
      <p>
        Latest sync #{run.id}: {run.status}
        {run.trigger ? ` · ${run.trigger}` : ""}
        {run.finished_at ? ` · ${formatSyncedAt(run.finished_at)}` : ""}
      </p>
      {entries.length > 0 ? (
        <ul className="mt-2 divide-y divide-border rounded-md border border-border bg-background">
          {entries.map(([source, detail]) => {
            const row = detail as SyncSourceDetail;
            const note = row.reason || row.error;
            return (
              <li key={source} className="flex flex-col gap-0.5 px-3 py-2">
                <span className="font-medium capitalize text-foreground">{source}</span>
                <span>
                  {row.status}
                  {row.mode ? ` · ${row.mode}` : ""}
                  {row.status === "ok"
                    ? ` · ${row.posts ?? 0} posts, ${row.comments ?? 0} comments, ${row.releases ?? 0} releases`
                    : ""}
                </span>
                {note ? <span className="text-destructive">{note}</span> : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mt-1">No per-platform details for this run.</p>
      )}
    </div>
  );
}

export function HomePage() {
  const [accounts, setAccounts] = useState<AccountStatus[] | null>(null);
  const [latest, setLatest] = useState<SyncRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [showSyncDetails, setShowSyncDetails] = useState(false);

  async function loadStatus() {
    setError(null);
    const data = await api.syncStatus();
    setAccounts(data.accounts);
    setLatest(data.latest_run);
  }

  useEffect(() => {
    let cancelled = false;
    loadStatus().catch((err: Error) => {
      if (!cancelled) setError(err.message);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function retryLoad() {
    try {
      await loadStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load status");
    }
  }

  async function refresh() {
    setSyncing(true);
    try {
      const result = await api.syncRefresh();
      if (result.status === "running") {
        if (result.toast.type === "warning") toast(result.toast.message);
        else toast.message(result.toast.message);
        const runId = result.run_id;
        const deadline = Date.now() + 10 * 60 * 1000;
        while (Date.now() < deadline) {
          await new Promise((r) => setTimeout(r, 1500));
          const status = await api.syncStatus();
          setAccounts(status.accounts);
          setLatest(status.latest_run);
          const latest = status.latest_run;
          if (!latest) continue;
          if (runId != null && latest.id !== runId) continue;
          if (latest.status === "running") continue;
          if (latest.status === "success") toast.success("Sync success");
          else if (latest.status === "partial") toast("Sync partial");
          else toast.error(`Sync ${latest.status}`);
          return;
        }
        toast("Sync still running — check back in a minute");
        return;
      }
      if (result.toast.type === "success") toast.success(result.toast.message);
      else if (result.toast.type === "warning") toast(result.toast.message);
      else toast.error(result.toast.message);
      await loadStatus();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div className="grain-header min-h-full">
      <div className="mx-auto max-w-3xl px-4 py-10 md:py-14">
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="flex flex-col gap-4"
        >
          <Logo variant="accent" className="size-12" />
          <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">ArtistAssist</h1>
          <p className="text-lg text-muted-foreground">Your social media assistant</p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" onClick={refresh} disabled={syncing}>
              {syncing ? "Syncing…" : "Refresh sync"}
            </Button>
          </div>
        </motion.div>

        <section className="mt-10 space-y-3">
          <div className="flex items-center gap-1.5">
            <h2 className="text-sm font-medium">Connection status</h2>
            {latest ? (
              <button
                type="button"
                className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-expanded={showSyncDetails}
                aria-controls="latest-sync-details"
                title="Show last sync result"
                onClick={() => setShowSyncDetails((open) => !open)}
              >
                <Info className="size-4" aria-hidden />
                <span className="sr-only">
                  {showSyncDetails ? "Hide last sync result" : "Show last sync result"}
                </span>
              </button>
            ) : null}
          </div>

          {showSyncDetails && latest ? (
            <div id="latest-sync-details">
              <SyncDetails run={latest} />
            </div>
          ) : null}

          {error ? (
            <ErrorState title="Could not load status" description={error} onRetry={retryLoad} />
          ) : null}
          {!error && accounts === null ? <LoadingState label="Loading connections…" /> : null}
          {accounts && accounts.length === 0 ? (
            <EmptyState
              title="No platforms synced yet"
              description="Run a refresh to pull your catalog and social posts."
              action={
                <Button type="button" size="sm" onClick={refresh}>
                  Run first sync
                </Button>
              }
            />
          ) : null}
          {accounts && accounts.length > 0 ? (
            <ul className="divide-y divide-border border border-border rounded-md">
              {accounts.map((a) => {
                const badge = statusBadge(a.status);
                const syncedAt = formatSyncedAt(a.last_synced_at);
                const needsAuth = a.status === "needs_auth" || a.status === "disconnected";
                const subtitle = accountSubtitle(a);
                return (
                  <li
                    key={a.source}
                    className="flex items-start justify-between gap-3 px-4 py-3 text-sm"
                  >
                    <div className="min-w-0 space-y-0.5">
                      <p className="font-medium capitalize">{a.source}</p>
                      {subtitle ? (
                        <p className="truncate text-xs text-muted-foreground">{subtitle}</p>
                      ) : null}
                      {syncedAt ? (
                        <p className="text-xs text-muted-foreground">Last synced {syncedAt}</p>
                      ) : null}
                      {a.status === "error" && a.last_error ? (
                        <p className="text-xs text-destructive">{a.last_error}</p>
                      ) : null}
                      {needsAuth ? (
                        <Link
                          to="/settings"
                          className="inline-block text-xs text-primary underline-offset-2 hover:underline"
                        >
                          Connect in Settings
                        </Link>
                      ) : null}
                    </div>
                    <span
                      className={cn(
                        "shrink-0 rounded-md border px-2 py-0.5 text-xs font-medium",
                        badge.className,
                      )}
                    >
                      {badge.label}
                    </span>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </section>
      </div>
    </div>
  );
}
