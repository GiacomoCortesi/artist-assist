# TikTok & YouTube notes

## TikTok Display API

Scopes used (read-only): `user.info.basic`, `user.info.stats`, `video.list`.

Sandbox apps can sync the developer's account; production app review is required
for broader access. No comments or reach fields — capabilities declare
`can_read_comments=False`.

## YouTube

- Data API v3 for channel, videos/Shorts, comments.
- Analytics API for daily views / watch time / subs (own channel OAuth).
- Google Cloud consent screen must be **In production** to reliably obtain
  refresh tokens for a single-user private deploy.
- Daily quota usage is stored in account `meta.quota` for Settings/Home — not
  Prometheus.
