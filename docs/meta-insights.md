# Meta insights metric notes (MVP)

Instagram Graph and Facebook Page insight metric names change over time.
ArtistAssist stores raw insight payloads on post `raw` / account `meta` when
fetched; context generation summarizes qualitative signals only (no dashboard).

## Instagram

Prefer `total_value` period metrics where Graph requires them for IG media insights
(e.g. reach / views depending on current docs). Map renamed metrics in sync by
keeping the platform's metric name as the key.

## Facebook Page

Use current Page Insights metric names from Graph docs at sync time. Persist
`metric → value` maps; do not hard-fail if a metric is missing — record
`no_data` for that metric.

## Threads

- Insights may be unavailable for content before 2024-06-01.
- Replies sync is top-level only (API caveat flag on account meta).

Publish scopes (`pages_manage_posts`, `instagram_content_publish`,
`threads_content_publish`) are never requested.
