# The Coriumist
Working repo for coriumist.com, the Desk, and the media pipeline.

## Layout
- `data/circuit.json`  the circuit: 40 cities, 191 venues, month weights and notes. Edit this to change the map, the Index and every city page.
- `tools/build.py`  the daily build. Computes today's Index read, the wire, and writes every page under `site/`.
- `site/`  what Netlify publishes as coriumist.com. Generated pages are overwritten each run; `read/`, `latest/`, `desk/` are hand-maintained.
- `.github/workflows/daily.yml`  the cron. Runs the build at 06:00 UTC daily and commits. Netlify redeploys on the commit.
- `desk/`  The Desk (coriumist-desk.netlify.app), publish dir for the second Netlify project.

## Rules
Operator is the publisher of record. Nothing in this repo publishes editorial content; it renders what is `status = published` in Supabase `content`.
Public sources, city and venue level, never an address.
