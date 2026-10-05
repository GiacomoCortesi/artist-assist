# Platform adapters

ArtistAssist talks to social and music platforms through a shared **read-only**
Python adapter interface (`app.adapters.base.PlatformAdapter`).

## Rules

- Official APIs only — **no scraping helpers**.
- Publish / schedule capabilities are always `false` for MVP.
- Outbound HTTP must send `User-Agent: ArtistAssist/<version>`.
- Never log access tokens; use `redact_secrets`.

## Adding a client

1. Subclass `PlatformAdapter`, set `source` to a `PlatformSource` value.
2. Implement `capabilities`, `fetch_profile`, and the iterators you need
   (`iter_posts`, `iter_comments`, `iter_catalog`).
3. Call `register_adapter(source, YourAdapter)`.
4. Prefer fixture/mocked HTTP in tests (`respx` or hand-rolled responses).
5. Wire the adapter into sync orchestration (AA-008) — sync consumes the
   interface, not concrete HTTP client internals.

## Retry policy

`with_retries` backs off on `RateLimitError` (exponential, capped). Other
`AdapterError` subclasses fail immediately so partial sync can record the error.
