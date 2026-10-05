import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { EmptyState, LoadingState } from "@/components/ui/states";
import {
  api,
  type StudioChatMessage,
  type StudioDraft,
  type StudioStreamEvent,
  type StudioThread,
} from "@/lib/api";

const PREVIEW_FRAMES: { id: string; label: string; aspect: string }[] = [
  { id: "feed_4x5", label: "Feed 4:5", aspect: "aspect-[4/5]" },
  { id: "square_1x1", label: "Square 1:1", aspect: "aspect-square" },
  { id: "story_9x16", label: "Story 9:16", aspect: "aspect-[9/16]" },
  { id: "landscape_16x9", label: "Landscape 16:9", aspect: "aspect-video" },
];

const SUGGESTIONS = [
  "Which Instagram post has the most likes?",
  "Draft an IG caption announcing my latest release",
  "Rewrite that caption shorter for TikTok",
];

type UiMessage = StudioChatMessage & { pending?: boolean; status?: string };

export function StudioPage() {
  const [threads, setThreads] = useState<StudioThread[] | null>(null);
  const [threadId, setThreadId] = useState<number | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [statusLine, setStatusLine] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<StudioDraft[] | null>(null);
  const [active, setActive] = useState<StudioDraft | null>(null);
  const [uploadedId, setUploadedId] = useState<number | null>(null);
  const [variants, setVariants] = useState<{ id: number; preset: string; path: string }[]>([]);
  const [focal, setFocal] = useState({ x: 0.5, y: 0.5 });
  const bottomRef = useRef<HTMLDivElement | null>(null);

  async function loadDrafts() {
    const list = await api.studioDrafts();
    setDrafts(list);
  }

  async function loadThreads() {
    const list = await api.studioThreads();
    setThreads(list);
  }

  async function openThread(id: number) {
    const detail = await api.studioGetThread(id);
    setThreadId(detail.id);
    setMessages(detail.messages ?? []);
  }

  async function ensureThread(): Promise<number> {
    if (threadId != null) return threadId;
    const created = await api.studioCreateThread();
    setThreadId(created.id);
    setThreads((prev) => (prev ? [created, ...prev] : [created]));
    return created.id;
  }

  useEffect(() => {
    void loadDrafts();
    void loadThreads().then(async () => {
      const list = await api.studioThreads();
      if (list[0]) {
        await openThread(list[0].id);
      }
    });
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, statusLine]);

  async function newChat() {
    const created = await api.studioCreateThread();
    setThreadId(created.id);
    setMessages([]);
    setStatusLine(null);
    setThreads((prev) => (prev ? [created, ...prev] : [created]));
  }

  function applyStreamEvent(event: StudioStreamEvent) {
    const type = event.type;
    switch (type) {
      case "user":
        setMessages((prev) => [
          ...prev,
          { id: event.id ?? Date.now(), role: "user", content: event.content ?? "" },
        ]);
        break;
      case "tool_start":
        setStatusLine(`Using ${event.name ?? "tool"}…`);
        break;
      case "tool_result":
        setStatusLine(`Got ${event.name ?? "tool"} result`);
        break;
      case "message":
        if (event.content) {
          setMessages((prev) => {
            const withoutPending = prev.filter((m) => !m.pending);
            return [
              ...withoutPending,
              {
                id: event.message_id ?? Date.now(),
                role: "assistant",
                content: event.content,
              },
            ];
          });
        }
        break;
      case "done":
        if (event.content) {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant" && last.content === event.content) {
              return prev.map((m, i) =>
                i === prev.length - 1
                  ? { ...m, id: event.message_id ?? m.id }
                  : m,
              );
            }
            const withoutPending = prev.filter((m) => !m.pending);
            return [
              ...withoutPending,
              {
                id: event.message_id ?? Date.now(),
                role: "assistant",
                content: event.content,
              },
            ];
          });
        }
        setStatusLine(null);
        break;
      case "draft_updated":
        if (event.draft) {
          setActive(event.draft);
          void loadDrafts();
          toast.success(`Draft #${event.draft.id} saved`);
        }
        break;
      case "error":
        toast.error(event.message || "Agent error");
        setStatusLine(null);
        break;
      default:
        break;
    }
  }

  async function send(text?: string) {
    const content = (text ?? input).trim();
    if (!content || busy) return;
    setBusy(true);
    setInput("");
    setStatusLine("Thinking…");
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: "user", content, pending: true },
    ]);
    try {
      const id = await ensureThread();
      // Replace optimistic user bubble — stream will re-emit user event
      setMessages((prev) => prev.filter((m) => !m.pending));
      await api.studioStreamMessage(id, content, applyStreamEvent);
      await loadThreads();
      await loadDrafts();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Send failed");
      setStatusLine(null);
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(file: File | null) {
    if (!file) return;
    try {
      const res = await api.uploadMedia(file);
      setUploadedId(res.id);
      toast.success(`Uploaded ${res.filename}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    }
  }

  async function adapt() {
    if (!uploadedId) {
      toast.message("Upload an original first");
      return;
    }
    try {
      const res = await api.adaptMedia(uploadedId, focal);
      setVariants(res.variants);
      toast.success(`Created ${res.variants.length} variants`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Adapt failed");
    }
  }

  async function exportDraft(id: number) {
    const pkg = await api.studioExport(id);
    const text = [pkg.caption, (pkg.hashtags || []).join(" "), pkg.note].filter(Boolean).join("\n\n");
    await navigator.clipboard.writeText(text);
    toast.success("Export package copied — publish manually outside ArtistAssist");
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Content Studio — ArtistAssist</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            AI Studio helps you plan, design, and create your social media content.
          </p>
        </div>
        <Button type="button" variant="secondary" onClick={() => void newChat()}>
          New chat
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section className="flex min-h-[28rem] flex-col rounded-md border border-border bg-background/60">
          <div className="flex-1 space-y-3 overflow-y-auto p-4">
            {messages.length === 0 ? (
              <EmptyState
                title="Start a conversation"
                description="Ask for captions, rankings from synced posts, or a rewrite. Try a suggestion below."
              />
            ) : (
              messages.map((m) => (
                <div
                  key={`${m.role}-${m.id}`}
                  className={`max-w-[90%] rounded-md px-3 py-2 text-sm whitespace-pre-wrap ${
                    m.role === "user"
                      ? "ml-auto bg-primary/15 text-foreground"
                      : "mr-auto bg-secondary/50 text-foreground"
                  }`}
                >
                  {m.content}
                </div>
              ))
            )}
            {statusLine ? (
              <p className="text-xs text-muted-foreground animate-pulse">{statusLine}</p>
            ) : null}
            <div ref={bottomRef} />
          </div>

          {messages.length === 0 ? (
            <div className="flex flex-wrap gap-2 border-t border-border px-4 py-3">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  disabled={busy}
                  onClick={() => void send(s)}
                  className="rounded-md border border-border px-2.5 py-1.5 text-left text-xs text-muted-foreground hover:bg-secondary/40"
                >
                  {s}
                </button>
              ))}
            </div>
          ) : null}

          <form
            className="flex gap-2 border-t border-border p-3"
            onSubmit={(e) => {
              e.preventDefault();
              void send();
            }}
          >
            <textarea
              className="min-h-12 max-h-40 flex-1 resize-y rounded-md border border-border bg-background p-2.5 text-sm"
              placeholder="Message the agent…"
              value={input}
              disabled={busy}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
            />
            <Button type="submit" disabled={busy || !input.trim()}>
              {busy ? "…" : "Send"}
            </Button>
          </form>
        </section>

        <aside className="space-y-4">
          <section className="space-y-2">
            <h2 className="text-sm font-medium">Chats</h2>
            {threads === null ? <LoadingState /> : null}
            {threads && threads.length === 0 ? (
              <p className="text-xs text-muted-foreground">No chats yet.</p>
            ) : (
              <ul className="max-h-40 space-y-1 overflow-y-auto text-sm">
                {threads?.map((t) => (
                  <li key={t.id}>
                    <button
                      type="button"
                      onClick={() => void openThread(t.id)}
                      className={`w-full rounded-md px-2 py-1.5 text-left text-xs ${
                        t.id === threadId ? "bg-primary/10" : "hover:bg-secondary/40"
                      }`}
                    >
                      {t.title || `Chat #${t.id}`}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-medium">Drafts</h2>
            {drafts === null ? <LoadingState /> : null}
            {drafts && drafts.length === 0 ? (
              <p className="text-xs text-muted-foreground">Ask the agent to save a caption.</p>
            ) : (
              <ul className="max-h-48 space-y-1 overflow-y-auto">
                {drafts?.map((d) => (
                  <li key={d.id}>
                    <button
                      type="button"
                      className="w-full rounded-md px-2 py-1.5 text-left text-xs hover:bg-secondary/40"
                      onClick={() => setActive(d)}
                    >
                      <p className="font-medium line-clamp-1">{d.title || `Draft #${d.id}`}</p>
                      <p className="text-muted-foreground line-clamp-1">{d.caption}</p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {active ? (
            <section className="space-y-2 rounded-md border border-border p-3">
              <h2 className="text-sm font-medium">Active draft</h2>
              <p className="text-xs whitespace-pre-wrap">{active.caption}</p>
              <p className="text-[11px] text-muted-foreground">{(active.hashtags || []).join(" ")}</p>
              <Button type="button" size="sm" variant="secondary" onClick={() => exportDraft(active.id)}>
                Copy export
              </Button>
            </section>
          ) : null}
        </aside>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-medium">Media adaptations</h2>
        <input
          type="file"
          accept="image/*"
          onChange={(e) => void onUpload(e.target.files?.[0] ?? null)}
          className="block text-sm"
        />
        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <label>
            Focal X
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={focal.x}
              onChange={(e) => setFocal((f) => ({ ...f, x: Number(e.target.value) }))}
              className="ml-2 align-middle"
            />
          </label>
          <label>
            Focal Y
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={focal.y}
              onChange={(e) => setFocal((f) => ({ ...f, y: Number(e.target.value) }))}
              className="ml-2 align-middle"
            />
          </label>
          <Button type="button" size="sm" onClick={adapt}>
            Adapt formats
          </Button>
        </div>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {PREVIEW_FRAMES.map((frame) => {
            const variant = variants.find((v) => v.preset === frame.id);
            return (
              <div key={frame.id} className="space-y-1">
                <div
                  className={`${frame.aspect} w-full rounded-md border border-border bg-secondary/40 flex items-center justify-center text-[10px] text-muted-foreground`}
                >
                  {variant ? variant.preset : frame.label}
                </div>
                <p className="text-[11px] text-muted-foreground">{frame.label}</p>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
