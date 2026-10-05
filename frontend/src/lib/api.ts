/** Thin API client for ArtistAssist backend (same-origin via Caddy/Vite proxy). */

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const TRANSIENT_STATUSES = new Set([502, 503, 504]);
const TRANSIENT_RETRIES = 4;
const TRANSIENT_DELAY_MS = 400;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: HeadersInit = { ...init?.headers };
  if (!(init?.body instanceof FormData) && !("Content-Type" in (headers as Record<string, string>))) {
    (headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  const method = (init?.method ?? "GET").toUpperCase();
  const retryable = method === "GET" || method === "HEAD";
  let attempt = 0;
  for (;;) {
    const res = await fetch(`/api${path}`, { ...init, headers });
    if (res.ok) {
      if (res.status === 204) {
        return undefined as T;
      }
      return res.json() as Promise<T>;
    }
    const text = await res.text();
    const shouldRetry =
      retryable && TRANSIENT_STATUSES.has(res.status) && attempt < TRANSIENT_RETRIES;
    if (!shouldRetry) {
      throw new ApiError(res.status, text || res.statusText);
    }
    attempt += 1;
    await sleep(TRANSIENT_DELAY_MS * attempt);
  }
}

export const api = {
  syncStatus: () => request<SyncStatus>("/sync/status"),
  syncRefresh: (sources?: string[]) =>
    request<SyncResult>("/sync/refresh", {
      method: "POST",
      body: JSON.stringify(sources ? { sources } : {}),
    }),
  contextList: () => request<ContextDoc[]>("/context"),
  contextUpdate: (slug: string, body: Partial<ContextDoc>) =>
    request<{ ok: boolean }>(`/context/${slug}`, { method: "PUT", body: JSON.stringify(body) }),
  contextRegen: () => request<{ ok: boolean }>("/context/regenerate", { method: "POST", body: "{}" }),
  getSettings: () => request<AppSettings>("/settings"),
  putSettings: (body: { artist_links?: Record<string, string>; display_name?: string }) =>
    request<{ ok: boolean }>("/settings", { method: "PUT", body: JSON.stringify(body) }),
  studioDrafts: () => request<StudioDraft[]>("/studio/drafts"),
  studioExport: (id: number) => request<ExportPackage>(`/studio/drafts/${id}/export`),
  studioThreads: () => request<StudioThread[]>("/studio/threads"),
  studioCreateThread: (title?: string) =>
    request<StudioThread>("/studio/threads", {
      method: "POST",
      body: JSON.stringify(title ? { title } : {}),
    }),
  studioGetThread: (id: number) => request<StudioThreadDetail>(`/studio/threads/${id}`),
  studioStreamMessage: async (
    threadId: number,
    content: string,
    onEvent: (event: StudioStreamEvent) => void,
  ) => {
    const res = await fetch(`/api/studio/threads/${threadId}/messages/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ content }),
    });
    if (!res.ok) {
      throw new ApiError(res.status, await res.text());
    }
    if (!res.body) {
      throw new ApiError(500, "No stream body");
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        const line = part
          .split("\n")
          .map((l) => l.trim())
          .find((l) => l.startsWith("data:"));
        if (!line) continue;
        const raw = line.slice(5).trim();
        if (!raw) continue;
        try {
          onEvent(JSON.parse(raw) as StudioStreamEvent);
        } catch {
          // ignore malformed chunks
        }
      }
    }
  },
  uploadMedia: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/media/upload", { method: "POST", body: form });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.json() as Promise<{ id: number; filename: string }>;
  },
  adaptMedia: (mediaId: number, focalPoint?: { x: number; y: number }) =>
    request<{ original_id: number; variants: { id: number; preset: string; path: string }[] }>(
      "/media/adapt",
      {
        method: "POST",
        body: JSON.stringify({ media_id: mediaId, focal_point: focalPoint }),
      },
    ),
  youtubeQuota: () => request<{ used: number; limit: number; remaining: number }>("/quota/youtube"),
  musicSearch: (source: string, q: string) =>
    request<IdentityHit[]>(
      `/music/search?source=${encodeURIComponent(source)}&q=${encodeURIComponent(q)}`,
    ),
  musicConfirm: (source: string, external_id: string, display_name?: string) =>
    request<{ ok: boolean }>("/music/confirm", {
      method: "POST",
      body: JSON.stringify({ source, external_id, display_name }),
    }),
};

export type SyncStatus = {
  accounts: AccountStatus[];
  latest_run: SyncRun | null;
};

export type AccountStatus = {
  source: string;
  status: string;
  last_synced_at?: string | null;
  last_error?: string | null;
  external_id?: string | null;
  display_name?: string | null;
  username?: string | null;
  no_data?: boolean;
  meta?: Record<string, unknown> | null;
};

export type SyncRun = {
  id: number;
  status: string;
  trigger: string;
  started_at?: string | null;
  finished_at?: string | null;
  per_source?: Record<string, unknown> | null;
};

export type SyncResult = {
  run_id: number | null;
  status: string;
  per_source: Record<string, unknown>;
  toast: { type: string; message: string };
};

export type ContextDoc = {
  id?: number;
  slug: string;
  title: string;
  body_markdown: string;
  section_locks?: Record<string, boolean> | null;
};

export type AppSettings = {
  artist_links: Record<string, string>;
  profile: { display_name?: string };
  platform_live: boolean;
  llm_live: boolean;
};

export type StudioDraft = {
  id: number;
  title?: string | null;
  caption?: string | null;
  hashtags?: string[] | null;
  platforms?: string[] | null;
  status?: string;
  thread_id?: number | null;
};

export type StudioThread = {
  id: number;
  title?: string | null;
  status?: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type StudioChatMessage = {
  id: number;
  role: "user" | "assistant" | string;
  content?: string | null;
  tool_name?: string | null;
  created_at?: string | null;
};

export type StudioThreadDetail = StudioThread & {
  messages: StudioChatMessage[];
};

export type StudioStreamEvent = {
  type: string;
  content?: string;
  name?: string;
  arguments?: Record<string, unknown>;
  draft?: StudioDraft;
  message?: string;
  message_id?: number;
  thread_id?: number;
  id?: number;
};

export type ExportPackage = {
  caption?: string | null;
  hashtags?: string[] | null;
  note: string;
};

export type IdentityHit = {
  source: string;
  external_id: string;
  name?: string;
  display_name?: string;
};
