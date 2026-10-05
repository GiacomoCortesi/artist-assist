import { useEffect, useState } from "react";
import { toast } from "sonner";

import { PlatformIcon, platformDisplayName } from "@/components/brand/PlatformIcon";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/ui/states";
import { api, type AccountStatus, type AppSettings, type IdentityHit } from "@/lib/api";
import { useTheme, type ThemeMode } from "@/lib/theme";

const THEMES: ThemeMode[] = ["system", "light", "dark"];
const MUSIC_SOURCES = ["spotify", "soundcloud", "deezer"] as const;

function extractPlatformId(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) return "";
  const artistMatch = trimmed.match(/\/artist\/(\d+|[\w]+)/i);
  if (artistMatch?.[1]) return artistMatch[1];
  const openSpotify = trimmed.match(/open\.spotify\.com\/artist\/([a-zA-Z0-9]+)/i);
  if (openSpotify?.[1]) return openSpotify[1];
  return trimmed;
}

export function SettingsPage() {
  const { theme, setTheme, resolved } = useTheme();
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [linksText, setLinksText] = useState("{}");
  const [displayName, setDisplayName] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);
  const [searchQ, setSearchQ] = useState("");
  const [searchSource, setSearchSource] = useState<string>("deezer");
  const [hits, setHits] = useState<IdentityHit[]>([]);
  const [searching, setSearching] = useState(false);
  const [manualIds, setManualIds] = useState<Record<string, string>>({
    spotify: "",
    soundcloud: "",
    deezer: "",
  });
  const [savingSource, setSavingSource] = useState<string | null>(null);
  const [musicAccounts, setMusicAccounts] = useState<AccountStatus[]>([]);
  const [quota, setQuota] = useState<{ used: number; limit: number; remaining: number } | null>(null);

  async function refreshMusicAccounts() {
    try {
      const status = await api.syncStatus();
      const music = status.accounts.filter((a) =>
        MUSIC_SOURCES.includes(a.source as (typeof MUSIC_SOURCES)[number]),
      );
      setMusicAccounts(music);
      setManualIds((prev) => {
        const next = { ...prev };
        for (const account of music) {
          if (account.external_id) next[account.source] = account.external_id;
        }
        return next;
      });
    } catch {
      // non-fatal on settings page
    }
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getSettings(), api.syncStatus()])
      .then(([s, status]) => {
        if (cancelled) return;
        setSettings(s);
        setLinksText(JSON.stringify(s.artist_links || {}, null, 2));
        setDisplayName(s.profile?.display_name || "");
        const music = status.accounts.filter((a) =>
          MUSIC_SOURCES.includes(a.source as (typeof MUSIC_SOURCES)[number]),
        );
        setMusicAccounts(music);
        setManualIds((prev) => {
          const next = { ...prev };
          for (const account of music) {
            if (account.external_id) next[account.source] = account.external_id;
          }
          return next;
        });
      })
      .catch((err: Error) => {
        if (!cancelled) setLoadError(err.message || "Failed to load settings");
      });
    api.youtubeQuota().then(setQuota).catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  async function save() {
    setSavingProfile(true);
    try {
      let artist_links: Record<string, string> = {};
      try {
        const parsed = JSON.parse(linksText.trim() || "{}") as unknown;
        if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
          throw new Error("Artist links must be a JSON object");
        }
        artist_links = parsed as Record<string, string>;
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Invalid JSON in artist links");
        return;
      }
      await api.putSettings({ artist_links, display_name: displayName });
      setSettings((prev) =>
        prev
          ? { ...prev, artist_links, profile: { ...prev.profile, display_name: displayName } }
          : prev,
      );
      toast.success("Settings saved");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSavingProfile(false);
    }
  }

  async function search() {
    if (!searchQ.trim()) {
      toast.error("Enter an artist name to search");
      return;
    }
    setSearching(true);
    try {
      const results = await api.musicSearch(searchSource, searchQ.trim());
      setHits(results);
      if (results.length === 0) toast("No matches");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  }

  async function saveIdentity(source: string, externalId: string, displayNameHint?: string) {
    const id = extractPlatformId(externalId);
    if (!id) {
      toast.error("Enter a platform artist id or profile URL");
      return;
    }
    setSavingSource(source);
    try {
      await api.musicConfirm(source, id, displayNameHint || displayName || undefined);
      setManualIds((prev) => ({ ...prev, [source]: id }));
      await refreshMusicAccounts();
      toast.success(`Saved ${source} identity (${id})`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save identity");
    } finally {
      setSavingSource(null);
    }
  }

  async function confirm(hit: IdentityHit) {
    await saveIdentity(hit.source, hit.external_id, hit.name || hit.display_name);
  }

  return (
    <div className="mx-auto max-w-2xl space-y-10 px-4 py-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings — ArtistAssist</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Connections, theme, and static artist links. Publishing is not available in this app.
        </p>
        {loadError ? <p className="mt-2 text-xs text-destructive">{loadError}</p> : null}
        {settings ? (
          <p className="mt-2 text-xs text-muted-foreground">
            Platform sync: {settings.platform_live ? "live" : "fixtures"} · LLM:{" "}
            {settings.llm_live ? "live" : "mocked"}
          </p>
        ) : !loadError ? (
          <LoadingState label="Loading settings…" />
        ) : null}
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-medium">Appearance</h2>
        <p className="text-xs text-muted-foreground">
          Current: {theme} (resolved {resolved})
        </p>
        <div className="flex flex-wrap gap-2">
          {THEMES.map((mode) => (
            <Button
              key={mode}
              type="button"
              variant={theme === mode ? "default" : "outline"}
              size="sm"
              onClick={() => setTheme(mode)}
            >
              {mode.charAt(0).toUpperCase() + mode.slice(1)}
            </Button>
          ))}
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium">Artist profile</h2>
        <label className="block text-xs text-muted-foreground">
          Display name
          <input
            className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
        </label>
        <label className="block text-xs text-muted-foreground">
          Static links (JSON)
          <textarea
            className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs min-h-28"
            value={linksText}
            onChange={(e) => setLinksText(e.target.value)}
          />
        </label>
        <Button type="button" onClick={save} disabled={savingProfile}>
          {savingProfile ? "Saving…" : "Save profile"}
        </Button>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium">Music identity</h2>
        <p className="text-sm text-muted-foreground">
          Paste a Deezer/Spotify/SoundCloud artist id or profile URL, or search and confirm. Saved
          ids are used on the next sync.
        </p>

        {musicAccounts.some((a) => a.display_name || a.external_id) ? (
          <ul className="divide-y divide-border rounded-md border border-border text-sm">
            {musicAccounts
              .filter((a) => a.display_name || a.external_id)
              .map((a) => {
                const detail = [a.display_name, a.external_id].filter(Boolean).join(" · ");
                return (
                  <li key={a.source} className="flex justify-between gap-2 px-3 py-2">
                    <span className="inline-flex items-center gap-2 font-medium">
                      <PlatformIcon source={a.source} />
                      {platformDisplayName(a.source)}
                    </span>
                    {detail ? (
                      <span className="text-xs text-muted-foreground text-right">{detail}</span>
                    ) : null}
                  </li>
                );
              })}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">No music identities saved yet.</p>
        )}

        <div className="space-y-3 rounded-md border border-border p-3">
          <p className="text-xs font-medium">Save by id / URL</p>
          {MUSIC_SOURCES.map((source) => (
            <div key={source} className="flex flex-wrap items-end gap-2">
              <label className="flex-1 min-w-40 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1.5">
                  <PlatformIcon source={source} />
                  {platformDisplayName(source)}
                </span>
                <input
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm font-mono"
                  placeholder={
                    source === "deezer"
                      ? "165434897 or https://www.deezer.com/artist/…"
                      : "Artist id or profile URL"
                  }
                  value={manualIds[source] || ""}
                  onChange={(e) =>
                    setManualIds((prev) => ({ ...prev, [source]: e.target.value }))
                  }
                />
              </label>
              <Button
                type="button"
                size="sm"
                disabled={savingSource === source}
                onClick={() => saveIdentity(source, manualIds[source] || "")}
              >
                {savingSource === source ? "Saving…" : "Save"}
              </Button>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap gap-2">
          <div className="inline-flex items-center gap-2">
            <PlatformIcon source={searchSource} />
            <select
              className="rounded-md border border-border bg-background px-2 py-2 text-sm"
              value={searchSource}
              onChange={(e) => setSearchSource(e.target.value)}
            >
              {MUSIC_SOURCES.map((s) => (
                <option key={s} value={s}>
                  {platformDisplayName(s)}
                </option>
              ))}
            </select>
          </div>
          <input
            className="flex-1 min-w-40 rounded-md border border-border bg-background px-3 py-2 text-sm"
            placeholder="Search artist name"
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void search();
              }
            }}
          />
          <Button type="button" variant="secondary" onClick={search} disabled={searching}>
            {searching ? "Searching…" : "Search"}
          </Button>
        </div>
        <ul className="space-y-2">
          {hits.map((hit) => (
            <li
              key={`${hit.source}-${hit.external_id}`}
              className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2 text-sm"
            >
              <span className="inline-flex items-center gap-2">
                <PlatformIcon source={hit.source} />
                <span>
                  {hit.name || hit.display_name}{" "}
                  <span className="text-xs text-muted-foreground">({hit.external_id})</span>
                </span>
              </span>
              <Button
                type="button"
                size="sm"
                disabled={savingSource === hit.source}
                onClick={() => confirm(hit)}
              >
                Save
              </Button>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-2">
        <h2 className="inline-flex items-center gap-2 text-sm font-medium">
          <PlatformIcon source="youtube" />
          YouTube quota
        </h2>
        {quota ? (
          <p className="text-sm text-muted-foreground">
            Used {quota.used} / {quota.limit} (remaining {quota.remaining})
          </p>
        ) : (
          <p className="text-sm text-muted-foreground">No quota data yet — run a YouTube sync.</p>
        )}
      </section>

    </div>
  );
}
