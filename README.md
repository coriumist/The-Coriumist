# The Coriumist
Working repo for coriumist.com, the Desk, and the media pipeline.

## Layout
- `data/circuit.json`  the circuit: 40 cities, 607 rooms (kind: hotel, restaurant, attraction), month weights and notes. Edit this to change the map, the Index and every city page.
- `data/photos.json`  destination photography, several per city, written by `tools/photos.py`. Licensed only. Put operator picks in `data/photos-manual.json` and they take precedence.
- `tools/photos.py`  fetches photographs. Unsplash if the `UNSPLASH_ACCESS_KEY` secret is set, otherwise Wikimedia Commons (CC0 / CC BY / CC BY-SA / public domain).
- `tools/build.py`  the daily build. Index read, the wire, and every page under `site/` including `read/` (article view) and `latest/`.
- `site/`  what Netlify publishes as coriumist.com. Generated pages are overwritten each run. `desk/` is hand-maintained.
- `.github/workflows/daily.yml`  the cron. 06:00 UTC daily: photos, build, commit. Netlify redeploys on the commit. Also runnable from the Actions tab.

## Rules
Operator is the publisher of record. Nothing in this repo publishes editorial content; it renders what is `status = published` in Supabase `content`.
Public sources, city and venue level, never an address. Photography licensed and credited on the image.
