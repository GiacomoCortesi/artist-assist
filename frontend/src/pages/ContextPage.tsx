import { FileDown, RefreshCw, Save, ToggleLeft, ToggleRight } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { PlatformIcon, platformDisplayName } from "@/components/brand/PlatformIcon";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";
import { api, type ContextDoc } from "@/lib/api";

function contextNavMeta(doc: ContextDoc): { source: string | null; label: string } {
  const match = /^platform_(.+)$/.exec(doc.slug);
  if (match?.[1]) {
    return { source: match[1], label: platformDisplayName(match[1]) };
  }
  return { source: null, label: doc.title };
}

export function ContextPage() {
  const [docs, setDocs] = useState<ContextDoc[] | null>(null);
  const [active, setActive] = useState<string>("artist_profile");
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      const list = await api.contextList();
      setDocs(list);
      const doc = list.find((d) => d.slug === active) || list[0];
      if (doc) {
        setActive(doc.slug);
        setBody(doc.body_markdown);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const doc = docs?.find((d) => d.slug === active);
    if (doc) setBody(doc.body_markdown);
  }, [active, docs]);

  async function save() {
    setSaving(true);
    try {
      await api.contextUpdate(active, { body_markdown: body });
      toast.success("Context saved");
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function regen() {
    try {
      await api.contextRegen();
      toast.success("Context regenerated");
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Regen failed");
    }
  }

  async function toggleLock(section: string) {
    const doc = docs?.find((d) => d.slug === active);
    const locks = { ...(doc?.section_locks || {}) };
    locks[section] = !locks[section];
    await api.contextUpdate(active, { section_locks: locks });
    toast.message(locks[section] ? `Locked ${section}` : `Unlocked ${section}`);
    await load();
  }

  function exportMarkdown() {
    if (!docs || docs.length === 0) {
      toast.error("No context to export");
      return;
    }
    const parts = [
      "# ArtistAssist artist context",
      "",
      "Grounding context for this artist — paste into an LLM as background.",
      "",
    ];
    for (const d of docs) {
      const content = d.slug === active ? body : d.body_markdown;
      parts.push(`## ${d.title}`, "", content.trim(), "");
    }
    const markdown = parts.join("\n").trimEnd() + "\n";
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "artistassist-context.md";
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Context exported as markdown");
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Context — ArtistAssist</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            LLM-ready artist profile and platform notes. Locked sections survive regen.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={exportMarkdown}
            disabled={!docs || docs.length === 0}
          >
            <FileDown className="size-4" aria-hidden />
            Export
          </Button>
          <Button type="button" variant="secondary" onClick={regen}>
            <RefreshCw className="size-4" aria-hidden />
            Regenerate
          </Button>
          <Button type="button" onClick={save} disabled={saving}>
            <Save className="size-4" aria-hidden />
            Save
          </Button>
        </div>
      </div>

      {error ? <ErrorState className="mt-6" title="Failed" description={error} /> : null}
      {docs === null && !error ? <LoadingState /> : null}
      {docs && docs.length === 0 ? (
        <EmptyState
          className="mt-6"
          title="Context not generated yet"
          description="Run a sync from Home, then regenerate here."
        />
      ) : null}

      {docs && docs.length > 0 ? (
        <div className="mt-6 grid gap-4 md:grid-cols-[12rem_1fr]">
          <nav className="flex md:flex-col gap-1 overflow-x-auto">
            {docs.map((d) => {
              const { source, label } = contextNavMeta(d);
              return (
                <button
                  key={d.slug}
                  type="button"
                  onClick={() => setActive(d.slug)}
                  className={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm whitespace-nowrap ${
                    active === d.slug
                      ? "bg-secondary font-medium"
                      : "text-muted-foreground hover:bg-secondary/60"
                  }`}
                >
                  {source ? <PlatformIcon source={source} /> : null}
                  <span>{label}</span>
                </button>
              );
            })}
          </nav>
          <div className="space-y-3">
            <div className="flex flex-wrap gap-4">
              {["identity", "tone", "catalog"].map((s) => {
                const locked = Boolean(docs.find((d) => d.slug === active)?.section_locks?.[s]);
                const ToggleIcon = locked ? ToggleRight : ToggleLeft;
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => toggleLock(s)}
                    aria-pressed={locked}
                    className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <ToggleIcon
                      className={`size-5 ${locked ? "text-primary" : ""}`}
                      aria-hidden
                    />
                    <span className="capitalize">{s}</span>
                  </button>
                );
              })}
            </div>
            <textarea
              className="min-h-[28rem] w-full rounded-md border border-border bg-background p-3 font-mono text-xs leading-relaxed"
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
