#!/usr/bin/env python3
"""
THE CORIUMIST . DAILY BUILD

Reads data/circuit.json. Computes today's Index read for every city.
Diffs against yesterday's read to produce the wire. Writes every page
under site/. Run by .github/workflows/daily.yml at 06:00 UTC.

The math (v1, calendar-weighted):
  w(m)      month weight from the dataset, or the city's base if the month is silent
  w_today   w(this month) blended toward w(next month) by how far into the month we are
  score     round(w_today * 100)
  rings     1 to 7, bucketed from score. Rings are what the mark encodes.
  state     opening / open / closing / dispersing / flat / quiet, from level and slope
Operator scoring of the twelve dimensions layers on top of this in a later version.
Nothing here is a forecast. It is a read of the calendar as of today.
"""
import json, os, re, calendar, datetime as dt, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
DATA = json.load(open(os.path.join(ROOT, "data", "circuit.json")))
SB_URL = "https://ocvbhjgdxmggjjgumflg.supabase.co"
SB_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9jdmJoamdkeG1nZ2pqZ3VtZmxnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODM4OTE5MTAsImV4cCI6MjA5OTQ2NzkxMH0.R6hh_f-MjcYw6WiI7dZ_L_AVLyM0ugjxyoW9RceNU90"  # anon key: public by design, read-only under RLS
TODAY = dt.date.today()
DISCLAIMER = "The Coriumist Index is an intelligence visualization tool. This is not financial advice or investment guidance."

# ----------------------------------------------------------------- math

def w_month(city, m):
    m = ((m - 1) % 12) + 1
    return city["months"].get(str(m), {}).get("w", city["base"])

def read_city(city, day):
    m, d = day.month, day.day
    dim = calendar.monthrange(day.year, m)[1]
    f = (d - 1) / dim
    w0, w1, wp = w_month(city, m), w_month(city, m + 1), w_month(city, m - 1)
    w = w0 * (1 - f) + w1 * f
    slope = w1 - w0
    score = round(w * 100)
    rings = 7 if score >= 85 else 6 if score >= 70 else 5 if score >= 55 else 4 if score >= 40 else 3 if score >= 25 else 2 if score >= 12 else 1
    if w >= 0.6 and slope > 0.15 and f < 0.5: state = "opening"
    elif w >= 0.6 and slope < -0.15 and f >= 0.5: state = "closing"
    elif w >= 0.6: state = "open"
    elif wp >= 0.6 and w < 0.6: state = "dispersing"
    elif city["tier"] == 1 and w < 0.45: state = "flat"
    elif slope > 0.2: state = "opening"
    else: state = "quiet"
    note = city["months"].get(str(m), {}).get("note") or city["why"]
    return {"slug": city["slug"], "name": city["name"], "tier": city["tier"], "lat": city["lat"], "lon": city["lon"],
            "score": score, "rings": rings, "state": state, "slope": round(slope, 2), "note": note,
            "year": [round(w_month(city, k) * 100) for k in range(1, 13)]}

reads = sorted((read_city(c, TODAY) for c in DATA["cities"]), key=lambda r: -r["score"])
prev_path = os.path.join(SITE, "data", "read.json")
prev = {}
if os.path.exists(prev_path):
    try: prev = {r["slug"]: r for r in json.load(open(prev_path))["cities"]}
    except Exception: prev = {}

wire = []
for r in reads:
    p = prev.get(r["slug"])
    if p and p["state"] != r["state"]:
        wire.append({"slug": r["slug"], "name": r["name"], "state": r["state"], "was": p["state"], "note": r["note"], "date": TODAY.isoformat()})
# keep a rolling wire so the page is never empty
old_wire = []
if os.path.exists(prev_path):
    try: old_wire = json.load(open(prev_path)).get("wire", [])
    except Exception: pass
seen = set(w["slug"] for w in wire)
wire += [w for w in old_wire if w["slug"] not in seen][:12 - len(wire)]
if not wire:  # first run: seed from the strongest signals
    for r in reads[:6]: wire.append({"slug": r["slug"], "name": r["name"], "state": r["state"], "was": None, "note": r["note"], "date": TODAY.isoformat()})

os.makedirs(os.path.join(SITE, "data"), exist_ok=True)
rooms = {c["slug"]: [{"n": v["name"], "s": v["slug"], "k": v["kind"]} for v in c["venues"]] for c in DATA["cities"]}
json.dump({"date": TODAY.isoformat(), "cities": reads, "wire": wire[:12], "rooms": rooms, "disclaimer": DISCLAIMER}, open(prev_path, "w"), indent=1, ensure_ascii=False)

# ----------------------------------------------------------------- shell

def esc(s): return html.escape(str(s), quote=True)
def date_long(d): return d.strftime("%A %-d %B %Y")
STATE_WORD = {"opening": "Opening", "open": "Open", "closing": "Closing", "dispersing": "Dispersing", "flat": "Flat", "quiet": "Quiet"}
TIER_WORD = {1: "Permanent capital", 2: "Seasonal capital", 3: "Floating capital"}

def mark_svg(rings=4, size=54):
    paths = ["M50 8c11 0 18 6 26 10s14 12 16 22-2 20-6 30-12 18-22 20-22-2-30-8S12 66 10 56s2-22 8-30 14-18 32-18z",
             "M50 21c8 0 13 4 19 7s10 9 11 16-1 15-4 22-9 13-16 15-16-2-22-6-12-11-13-18 1-16 6-22 10-14 19-14z",
             "M50 34c5 0 9 2 12 5s6 6 7 10-1 9-3 13-6 8-10 9-10-1-14-4-7-7-8-11 1-10 4-14 7-8 12-8z",
             "M50 46c3 0 5 1 6 3s3 3 3 5-1 4-2 6-3 4-5 4-5-1-7-2-4-3-4-5 1-5 2-7 4-4 7-4z"]
    return f'<svg viewBox="0 0 100 100" width="{size}" height="{size}" aria-hidden="true" fill="none" stroke="#2f5d3f" stroke-width="5.2" stroke-linejoin="round">' + "".join(f'<path d="{p}"/>' for p in paths) + "</svg>"

CSS = """
:root{--ink:#2f5d3f;--paper:#f7f3e9;--rule:rgba(47,93,63,.28);--rule-strong:rgba(47,93,63,.55);--mute:rgba(47,93,63,.68);--w:1180px}
*{box-sizing:border-box;margin:0;padding:0}
html{background:var(--paper);color:var(--ink);-webkit-font-smoothing:antialiased}
body{font-family:"Fraunces",Georgia,serif;font-variation-settings:"opsz" 18,"wght" 400;font-size:17px;line-height:1.55}
a{color:inherit;text-decoration:none}a:hover{text-decoration:underline;text-underline-offset:3px;text-decoration-thickness:1px}
a:focus-visible,button:focus-visible,input:focus-visible{outline:1.5px solid var(--ink);outline-offset:3px}
.mono{font-family:"Space Mono",ui-monospace,monospace;font-size:11px;letter-spacing:.06em;line-height:1.5}
.wrap{max-width:var(--w);margin:0 auto;padding:0 28px}
.top{display:flex;justify-content:space-between;align-items:baseline;padding:16px 0 10px;border-bottom:1px solid var(--rule-strong)}.top .r{color:var(--mute)}
.mast{display:flex;align-items:center;gap:22px;padding:22px 0 18px}.mast svg{flex:none}
.mast h1{font-variation-settings:"opsz" 144,"wght" 480;font-size:44px;line-height:1;letter-spacing:-.01em}.mast small{display:block;margin-top:8px}
nav.primary{border-top:1px solid var(--rule-strong);border-bottom:1px solid var(--rule)}nav.primary ul{display:flex;list-style:none;overflow-x:auto}nav.primary li a{display:block;padding:11px 22px 11px 0;white-space:nowrap}
nav.primary li a[aria-current]{text-decoration:underline;text-underline-offset:5px}
h2.big{font-variation-settings:"opsz" 144,"wght" 460;font-size:52px;line-height:1.02;letter-spacing:-.015em;max-width:16ch}
.dek{margin-top:18px;font-size:20px;line-height:1.4;max-width:36ch}
section{padding:30px 0 34px;border-bottom:1px solid var(--rule)}
.sec-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:22px}.sec-head .mono{color:var(--mute)}
.lede{padding:44px 0 34px;display:grid;grid-template-columns:2fr 1fr;gap:48px;border-bottom:1px solid var(--rule)}
.lede .circuit{border-left:1px solid var(--rule);padding-left:28px}
.path{margin-top:14px;font-variation-settings:"opsz" 40,"wght" 460;font-size:24px;line-height:1.4}.path a{display:block}
.path a::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--ink);margin:0 12px 3px 0}
.path a.faint{color:var(--mute)}.path a.faint::before{background:transparent;border:1px solid var(--mute);width:5px;height:5px}
.path .st{font-family:"Space Mono",monospace;font-size:11px;letter-spacing:.06em;color:var(--mute);margin-left:10px}
.wire{display:grid;grid-template-columns:repeat(3,1fr)}.wire article{padding:0 28px 18px 0;border-right:1px solid var(--rule);margin-bottom:18px}
.wire article:nth-child(n+2){padding-left:28px}.wire article:nth-child(3n){border-right:0;padding-right:0}
.wire .tag{display:flex;justify-content:space-between;margin-bottom:10px}.wire p{font-size:17px;line-height:1.45}
.facts{border-top:1px solid var(--rule-strong)}.facts dl{display:grid;grid-template-columns:1fr 1fr}
.facts div{padding:12px 0;border-bottom:1px solid var(--rule)}.facts div:nth-child(odd){padding-right:20px;border-right:1px solid var(--rule)}.facts div:nth-child(even){padding-left:20px}
.facts dt{color:var(--mute)}.facts dd{margin-top:5px;font-size:17px;line-height:1.35}
.disc{color:var(--mute);padding-top:14px}
.feature{display:grid;grid-template-columns:1fr 1fr;gap:56px;align-items:start}
.feature h3{font-variation-settings:"opsz" 144,"wght" 460;font-size:44px;line-height:1.05;letter-spacing:-.012em;margin:10px 0 18px}
.feature .standfirst{font-size:19px;line-height:1.45;max-width:38ch}
.read{display:inline-block;margin-top:22px;border-bottom:1px solid var(--ink);padding-bottom:2px}.read:hover{text-decoration:none;border-bottom-width:2px}
.filed article{display:grid;grid-template-columns:200px 1fr 220px;gap:32px;padding:22px 0;border-top:1px solid var(--rule)}.filed article:first-of-type{border-top:0;padding-top:0}
.filed h4{font-variation-settings:"opsz" 72,"wght" 460;font-size:30px;line-height:1.12;letter-spacing:-.01em;max-width:22ch}.filed p{margin-top:10px;max-width:60ch}
.filed .meta{color:var(--mute)}.filed .place{text-align:right}
.filed .place b{display:block;font-family:"Fraunces",serif;font-variation-settings:"opsz" 40,"wght" 460;font-size:18px;font-weight:normal;margin-bottom:6px;letter-spacing:0}
table.rank{width:100%;border-collapse:collapse}table.rank th{text-align:left;padding:8px 0;border-bottom:1px solid var(--rule-strong);color:var(--mute);font-weight:normal}
table.rank td{padding:12px 0;border-bottom:1px solid var(--rule);vertical-align:baseline}table.rank td.n{font-variation-settings:"opsz" 40,"wght" 460;font-size:20px}
table.rank td.num{font-family:"Space Mono",monospace;font-size:13px}
.year{display:grid;grid-template-columns:repeat(12,1fr);gap:6px;align-items:end;height:90px;border-bottom:1px solid var(--rule-strong)}
.year i{display:block;background:var(--ink);opacity:.9}.year i.now{opacity:.35}
.year-l{display:grid;grid-template-columns:repeat(12,1fr);gap:6px;margin-top:6px;color:var(--mute)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:56px;align-items:start}
.venues{list-style:none;columns:2;column-gap:40px}.venues li{padding:9px 0;border-bottom:1px solid var(--rule);break-inside:avoid}
.venues li .k{color:var(--mute);margin-left:10px}
.venues.one{columns:1}.three{display:grid;grid-template-columns:repeat(3,1fr);gap:32px}
.gate{display:grid;grid-template-columns:1fr 1fr;gap:56px;align-items:end}.gate h3{font-variation-settings:"opsz" 144,"wght" 460;font-size:34px;line-height:1.1;max-width:20ch}.gate p{margin-top:14px;max-width:44ch}
.gate form{display:flex;border-bottom:1px solid var(--ink)}.gate input{flex:1;border:0;background:transparent;font:inherit;color:var(--ink);padding:12px 0}.gate input::placeholder{color:var(--mute)}
.gate button{border:0;background:transparent;color:var(--ink);cursor:pointer;padding:12px 0 12px 16px}
footer{padding:36px 0 44px}.foot{display:grid;grid-template-columns:repeat(4,1fr);gap:28px;padding-bottom:36px;border-bottom:1px solid var(--rule)}.foot h5{margin-bottom:12px}.foot ul{list-style:none}.foot li{padding:3px 0}
.sign{display:flex;justify-content:space-between;align-items:center;padding-top:26px}.sign .line{font-variation-settings:"opsz" 40,"wght" 460;font-size:20px}.sign .mono{color:var(--mute)}
.crumb{color:var(--mute);padding:22px 0 0}
.prose{max-width:66ch}.prose p{margin:0 0 18px}
.dir{display:grid;grid-template-columns:repeat(3,1fr);gap:0}.dir a{display:block;padding:14px 20px 14px 0;border-bottom:1px solid var(--rule)}
.dir a b{display:block;font-weight:normal;font-variation-settings:"opsz" 40,"wght" 460;font-size:20px}.dir a span{color:var(--mute)}
@media (max-width:900px){
 .lede,.feature,.two,.gate{grid-template-columns:1fr;gap:28px}.lede{padding:34px 0 28px}h2.big{font-size:40px}
 .lede .circuit{border-left:0;padding-left:0;border-top:1px solid var(--rule);padding-top:22px}
 .wire{grid-template-columns:1fr}.wire article{border-right:0;padding:0 0 18px;border-bottom:1px solid var(--rule)}.wire article:nth-child(n+2){padding-left:0}
 .feature h3{font-size:34px}.filed article{grid-template-columns:1fr;gap:10px}.filed .place{text-align:left}
 .foot,.dir{grid-template-columns:1fr 1fr}.three{grid-template-columns:1fr}.mast h1{font-size:34px}.sign{flex-direction:column;align-items:flex-start;gap:12px}.venues{columns:1}
}
"""

NAV = [("Circuit", "/circuit/"), ("Places", "/places/"), ("The Games", "/the-games/"), ("The Index", "/index/"), ("The Map", "/map/"), ("Dispatches", "/read/")]

def shell(title, body, current=None, desc="Where capital congregates, by season and coordinate. Public record only.", extra_head=""):
    nav = "".join(f'<li><a href="{h}"{" aria-current=page" if h == current else ""}>{esc(n)}</a></li>' for n, h in NAV)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,480;9..144,520&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>{CSS}</style>{extra_head}</head>
<body><div class="wrap">
<div class="top mono"><span>{esc(date_long(TODAY))}</span><span class="r">Public record only. City and venue level.</span></div>
<header class="mast"><a href="/" aria-label="The Coriumist">{mark_svg()}</a><div><h1><a href="/">The Coriumist</a></h1><small class="mono">Where capital congregates. By season, by coordinate.</small></div></header>
<nav class="primary mono" aria-label="Primary"><ul>{nav}</ul></nav>
{body}
</div>
<footer><div class="wrap">
<div class="foot mono">
<div><h5>The circuit</h5><ul><li><a href="/circuit/">Cities</a></li><li><a href="/map/">Map</a></li><li><a href="/index/">The Index</a></li><li><a href="/places/">Places</a></li></ul></div>
<div><h5>The desk</h5><ul><li><a href="/read/">Dispatches</a></li><li><a href="/the-games/">The Games</a></li><li><a href="/latest/">Latest</a></li></ul></div>
<div><h5>The data</h5><ul><li><a href="/methodology/">Methodology</a></li><li><a href="/data/read.json">Today's read (JSON)</a></li></ul></div>
<div><h5>The Coriumist</h5><ul><li><a href="mailto:coriumist.ops@gmail.com">Contact</a></li><li><a href="https://www.instagram.com/coriumist">Instagram</a></li></ul></div>
</div>
<div class="sign"><span class="line">Money moves. We map it.</span><span class="mono">Public sources. City level. Never an address. The Coriumist, {TODAY.year}.</span></div>
</div></footer></body></html>"""

def write(path, content):
    full = os.path.join(SITE, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, "w").write(content)

SB_JS = f"""<script>
const SB="{SB_URL}",SK="{SB_KEY}";
async function sb(q){{try{{const r=await fetch(SB+"/rest/v1/"+q,{{headers:{{apikey:SK,Authorization:"Bearer "+SK}}}});return r.ok?await r.json():[]}}catch(e){{return[]}}}}
function fmtDate(s){{if(!s)return"";const d=new Date(s);return d.toLocaleDateString("en-GB",{{day:"numeric",month:"long",year:"numeric"}})}}
</script>"""

# (homepage is built at the end of this file, after the map component)
cities_by_slug = {c["slug"]: c for c in DATA["cities"]}


# ----------------------------------------------------------------- index (ranking)
rows = "".join(f'<tr><td class="num">{i+1:02d}</td><td class="n"><a href="/circuit/{r["slug"]}/">{esc(r["name"])}</a></td><td class="mono">{TIER_WORD[r["tier"]]}</td><td class="mono">{STATE_WORD[r["state"]]}</td><td class="num">{r["score"]}</td><td class="num">{"●"*r["rings"]}</td><td class="num">{"+" if r["slope"]>0 else ""}{r["slope"]:.2f}</td></tr>' for i, r in enumerate(reads))
idx = f"""
<div class="lede"><div><h2 class="big">The Index. Forty cities, one number each.</h2><p class="dek">Concentration of the circuit as of today, on a calendar-weighted read. Rings are the number the mark carries.</p></div>
<aside class="circuit"><div class="mono">Read date</div><div class="path"><span style="display:block;font-size:24px">{esc(date_long(TODAY))}</span></div><p class="mono" style="margin-top:16px;color:var(--mute)"><a href="/methodology/">How the number is made</a></p></aside></div>
<section><table class="rank"><thead><tr class="mono"><th></th><th>City</th><th>Tier</th><th>State</th><th>Score</th><th>Rings</th><th>Trend</th></tr></thead><tbody>{rows}</tbody></table>
<p class="disc mono">{DISCLAIMER}</p></section>"""
write("index/index.html", shell("The Coriumist Index", idx, "/index/"))

# ----------------------------------------------------------------- circuit directory
dir_html = "".join(f'<a href="/circuit/{r["slug"]}/"><b>{esc(r["name"])}</b><span class="mono">{TIER_WORD[r["tier"]]}. {STATE_WORD[r["state"]]}. {r["score"]}</span></a>' for r in sorted(reads, key=lambda r: (r["tier"], r["name"])))
write("circuit/index.html", shell("The Circuit. Cities", f'<div class="lede"><div><h2 class="big">The circuit. Forty cities.</h2><p class="dek">Ten permanent capitals that never disappear. Thirty seasonal capitals that become the centre of gravity and then stop.</p></div></div><section><div class="dir">{dir_html}</div></section>', "/circuit/"))

# ----------------------------------------------------------------- city pages
MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
for r in reads:
    c = cities_by_slug[r["slug"]]
    active = sorted(((int(k), v) for k, v in c["months"].items()), key=lambda x: x[0])
    peak = max(active, key=lambda x: x[1]["w"]) if active else None
    bars = "".join(f'<i class="{"now" if k+1==TODAY.month else ""}" style="height:{max(4, v)}%" title="{MON[k]} {v}"></i>' for k, v in enumerate(r["year"]))
    def vlist(kind): return "".join(f'<li><a href="/places/{c["slug"]}/{v["slug"]}/">{esc(v["name"])}</a><span class="k mono" data-v="{c["slug"]}/{v["slug"]}"></span></li>' for v in c["venues"] if v["kind"] == kind)
    ven = "".join(f'<div><h4 class="mono" style="margin-bottom:8px;color:var(--mute)">{lbl}</h4><ul class="venues one">{vlist(k)}</ul></div>' for k, lbl in (("hotel","Hotels"),("restaurant","Restaurants"),("attraction","Attractions and nightlife")))
    windows = "".join(f'<div><dt class="mono">{calendar.month_name[k]}</dt><dd>{esc(v["note"])}</dd></div>' for k, v in active)
    body = f"""
<p class="crumb mono"><a href="/circuit/">Circuit</a> / {esc(c["name"])}</p>
<div class="lede"><div><div class="mono">{TIER_WORD[c["tier"]]}</div><h2 class="big">{esc(c["name"])}</h2><p class="dek">{esc(c["why"])}</p></div>
<aside class="circuit"><div class="facts"><dl>
<div><dt class="mono">State today</dt><dd>{STATE_WORD[r["state"]]}</dd></div><div><dt class="mono">Score</dt><dd>{r["score"]}</dd></div>
<div><dt class="mono">Rings</dt><dd>{"●"*r["rings"]}</dd></div><div><dt class="mono">Trend</dt><dd>{"Rising" if r["slope"]>0.05 else "Falling" if r["slope"]<-0.05 else "Holding"}</dd></div>
<div><dt class="mono">Peak</dt><dd>{calendar.month_name[peak[0]] if peak else "Year round"}</dd></div><div><dt class="mono">Rooms</dt><dd>{len(c["venues"])}</dd></div>
</dl></div></aside></div>
<section><div class="sec-head"><h3 class="mono">The read, {esc(calendar.month_name[TODAY.month])}</h3></div><p class="dek" style="margin:0">{esc(r["note"])}</p></section>
<section><div class="sec-head"><h3 class="mono">The year</h3><span class="mono">Circuit weight by month</span></div><div class="year">{bars}</div><div class="year-l mono">{"".join(f"<span>{m}</span>" for m in MON)}</div></section>
<section><div class="sec-head"><h3 class="mono">The rooms</h3><span class="mono">Public venues. Coriumist Approved where designated.</span></div><div class="three">{ven}</div></section>
<section><div class="sec-head"><h3 class="mono">The windows</h3></div><div class="facts"><dl>{windows}</dl></div><p class="disc mono">{DISCLAIMER}</p></section>
{SB_JS}<script>(async()=>{{const v=await sb("venues?city_slug=eq.{c["slug"]}&approved=eq.true&select=slug");const s=new Set(v.map(x=>x.slug));document.querySelectorAll("[data-v]").forEach(e=>{{if(s.has(e.dataset.v.split("/")[1]))e.textContent="Coriumist Approved"}})}})();</script>"""
    write(f"circuit/{c['slug']}/index.html", shell(f"{c['name']}. The Coriumist Circuit", body, "/circuit/", desc=c["why"]))

# ----------------------------------------------------------------- places
def plist(c, kind): return "".join(f'<li><a href="/places/{c["slug"]}/{v["slug"]}/">{esc(v["name"])}</a></li>' for v in c["venues"] if v["kind"] == kind)
pl = "".join(f'<section><div class="sec-head"><h3 class="mono"><a href="/circuit/{c["slug"]}/">{esc(c["name"])}</a></h3><span class="mono">{len(c["venues"])} rooms</span></div><div class="three">' + "".join(f'<div><h4 class="mono" style="margin-bottom:8px;color:var(--mute)">{lbl}</h4><ul class="venues one">{plist(c,k)}</ul></div>' for k, lbl in (("hotel","Hotels"),("restaurant","Restaurants"),("attraction","Attractions and nightlife"))) + "</div></section>" for c in sorted(DATA["cities"], key=lambda c: (c["tier"], c["name"])))
write("places/index.html", shell("Places. The rooms on the circuit", f'<div class="lede"><div><h2 class="big">The rooms.</h2><p class="dek">Six hundred public venues where the circuit actually sits. Hotels, clubs, restaurants, beach clubs, marinas. The designation is ours. The address is theirs.</p></div></div>{pl}', "/places/"))

for c in DATA["cities"]:
    for v in c["venues"]:
        body = f"""
<p class="crumb mono"><a href="/places/">Places</a> / <a href="/circuit/{c["slug"]}/">{esc(c["name"])}</a> / {esc(v["name"])}</p>
<div class="lede"><div><div class="mono" id="v-status">On the map. Designation pending.</div><h2 class="big">{esc(v["name"])}</h2><p class="dek" id="v-what">{esc(c["name"])}. {esc(c["why"])}</p></div>
<aside class="circuit"><div class="facts"><dl>
<div><dt class="mono">City</dt><dd><a href="/circuit/{c["slug"]}/">{esc(c["name"])}</a></dd></div><div><dt class="mono">Kind</dt><dd id="v-kind">{ {"hotel":"Hotel","restaurant":"Restaurant","attraction":"Attraction or nightlife"}[v["kind"]] }</dd></div>
<div><dt class="mono">City state today</dt><dd>{STATE_WORD[next(r["state"] for r in reads if r["slug"]==c["slug"])]}</dd></div><div><dt class="mono">City score</dt><dd>{next(r["score"] for r in reads if r["slug"]==c["slug"])}</dd></div>
</dl></div></aside></div>
<section id="designation"><div class="sec-head"><h3 class="mono">Coriumist Approved</h3><span class="mono" id="v-date"></span></div>
<div class="prose"><p id="v-who" style="color:var(--mute)">The designation runs three sentences: what it is, who it attracts and why that matters, what to know before arriving. This room has not yet been designated.</p><p id="v-know"></p></div></section>
{SB_JS}<script>(async()=>{{const r=await sb("venues?city_slug=eq.{c["slug"]}&slug=eq.{v["slug"]}&select=kind,what,who,know,approved,updated_at");const d=r[0];if(!d)return;if(d.kind)document.getElementById("v-kind").textContent=d.kind;if(d.approved){{document.getElementById("v-status").textContent="Coriumist Approved";document.getElementById("v-what").textContent=d.what||"";const w=document.getElementById("v-who");w.style.color="";w.textContent=d.who||"";document.getElementById("v-know").textContent=d.know||"";document.getElementById("v-date").textContent="Designated "+fmtDate(d.updated_at)}}}})();</script>"""
        write(f"places/{c['slug']}/{v['slug']}/index.html", shell(f"{v['name']}, {c['name']}. Coriumist Approved", body, "/places/"))

# ----------------------------------------------------------------- the games
write("the-games/index.html", shell("The Games. The Coriumist", f"""
<div class="lede"><div><h2 class="big">The Games.</h2><p class="dek">Racing, sailing, tennis, polo, the paddock. Sport read as a capital event: who is in the box, what the box costs, and what the season is really for.</p></div></div>
<section class="filed"><div id="games-list"><p class="mono" style="color:var(--mute)">Nothing filed yet.</p></div></section>{SB_JS}
<script>(async()=>{{const rows=await sb("content?status=eq.published&format=ilike.*game*&select=id,format,title,body,publish_at&order=publish_at.desc&limit=40");const strip=b=>(b||"").replace(/<[^>]+>/g," ").replace(/\\s+/g," ").trim();if(rows.length)document.getElementById("games-list").innerHTML=rows.map(r=>`<article><div class="meta mono">${{fmtDate(r.publish_at)}}</div><div><h4><a href="/read/?id=${{r.id}}">${{r.title}}</a></h4><p>${{strip(r.body).slice(0,180)}}</p></div><div class="place mono"></div></article>`).join("")}})();</script>""", "/the-games/"))

# ----------------------------------------------------------------- methodology
write("methodology/index.html", shell("Methodology. The Coriumist", f"""
<div class="lede"><div><h2 class="big">How the number is made.</h2><p class="dek">Every city on the circuit carries one score, recomputed each morning. This is what is behind it.</p></div></div>
<section><div class="prose">
<p>The circuit is forty cities. Ten are permanent capitals and carry a standing weight all year. Thirty are seasonal and carry a weight only in the months the calendar puts them in play. Those weights come from the published calendar of the circuit: the fairs, the regattas, the races, the sales, the summits, and the rooms that fill around them.</p>
<p>Each day the score blends this month's weight toward next month's by how far into the month we are, so a place does not fall off a cliff on the first of the month. The result is a number from 0 to 100. The rings on the mark are that number in seven steps.</p>
<p>The state is read from the level and the slope. Opening when the weight is high and still rising early in the window. Open at full weight. Closing when the weight is high and the next month drops it. Dispersing in the month after a peak. Flat when a permanent capital sits below its usual line, which is its own signal. Quiet otherwise.</p>
<p>The wire records state changes only. A city appears on the wire when its state changed since yesterday's read. Nothing on the wire is a forecast.</p>
<p>The twelve dimensions of the Index (capital density, decision velocity, privacy, invitation threshold, repeat attendance, cross-sector convergence, yacht fleet, private aviation, family office concentration, luxury brand activation, auction and art market influence, hospitality heat) are scored by the operator and layered onto the calendar read as they are entered. Where a dimension has not been scored, the calendar read stands alone.</p>
<p>Sources are public only: published event calendars and notices of race, public attendance and speaker pages, filings, ADS-B broadcast at city aggregate. Outputs are city and venue level. Never an address, never an individual in real time.</p>
<p class="mono" style="color:var(--mute)">{DISCLAIMER}</p>
</div></section>""", None))

# ----------------------------------------------------------------- map (shared component)
MAP_CSS = """
#mfilter button{border:0;background:transparent;color:var(--mute);font:inherit;cursor:pointer;padding:0;border-bottom:1px solid transparent}#mfilter button.on{color:var(--ink);border-bottom-color:var(--ink)}
.land{fill:none;stroke:rgba(47,93,63,.35);stroke-width:.6}.gr{fill:none;stroke:rgba(47,93,63,.12);stroke-width:.5}
.city{cursor:pointer}.city circle{fill:none;stroke:#2f5d3f;stroke-width:1.1}.city circle.core{fill:#2f5d3f}.city.dim{opacity:.18}.city.sel circle{stroke-width:1.8}
.city circle.halo{stroke:none;fill:#2f5d3f;opacity:.18;transform-origin:center;animation:halo 2.6s ease-out infinite}
@keyframes halo{0%{transform:scale(.4);opacity:.35}80%{transform:scale(1.9);opacity:0}100%{opacity:0}}
.city text{font-family:"Space Mono",monospace;font-size:9px;fill:#2f5d3f;letter-spacing:.04em}
#panel{display:none;margin-top:18px;border-top:1px solid var(--rule-strong);padding-top:18px}
#panel .ph{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:12px}
#panel .ph h3{font-variation-settings:"opsz" 72,"wght" 460;font-size:34px;line-height:1.05}
#panel .pnote{margin:12px 0 20px;font-size:18px;max-width:60ch}
.rooms3{display:grid;grid-template-columns:repeat(3,1fr);gap:28px}.rooms3 h4{color:var(--mute);margin-bottom:8px}.rooms3 ul{list-style:none}.rooms3 li{padding:7px 0;border-bottom:1px solid var(--rule)}
.rooms3 li .ap{color:var(--mute);margin-left:8px}
@media (max-width:900px){.rooms3{grid-template-columns:1fr}#panel .ph h3{font-size:28px}}
"""
MAP_JS = f"""
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script><script src="https://cdnjs.cloudflare.com/ajax/libs/topojson/3.0.2/topojson.min.js"></script>
<script>
(async()=>{{
const read=await (await fetch("/data/read.json?d={TODAY.isoformat()}")).json();
const land=await (await fetch("/map/data/land-110m.json")).json();
const svg=d3.select("#map"),W=1180,H=560;
const proj=d3.geoNaturalEarth1().fitExtent([[10,10],[W-10,H-10]],{{type:"Sphere"}});
const path=d3.geoPath(proj);
svg.append("path").attr("class","gr").attr("d",path(d3.geoGraticule10()));
svg.append("path").attr("class","land").attr("d",path(topojson.feature(land,land.objects.land)));
const ST={{opening:"Opening",open:"Open",closing:"Closing",dispersing:"Dispersing",flat:"Flat",quiet:"Quiet"}};
const g=svg.append("g");
const cities=g.selectAll("g.city").data(read.cities).join("g").attr("class","city").attr("transform",d=>{{const p=proj([d.lon,d.lat]);return `translate(${{p[0]}},${{p[1]}})`}});
cities.each(function(d){{const s=d3.select(this);if(d.state==="open"||d.state==="opening")s.append("circle").attr("class","halo").attr("r",d.rings*2.6+4);
 for(let i=0;i<d.rings;i++)s.append("circle").attr("r",2.2+i*2.6);s.append("circle").attr("class","core").attr("r",1.6);
 if(d.rings>=4)s.append("text").attr("x",d.rings*2.6+6).attr("y",3).text(d.name)}});
let approved=new Set();
try{{const a=await (await fetch("{SB_URL}/rest/v1/venues?approved=eq.true&select=city_slug,slug",{{headers:{{apikey:"{SB_KEY}",Authorization:"Bearer {SB_KEY}"}}}})).json();approved=new Set(a.map(x=>x.city_slug+"/"+x.slug))}}catch(e){{}}
const panel=document.getElementById("panel");
function col(d,kind,label){{const rs=(read.rooms[d.slug]||[]).filter(r=>r.k===kind);return `<div><h4 class="mono">${{label}}</h4><ul>${{rs.map(r=>`<li><a href="/places/${{d.slug}}/${{r.s}}/">${{r.n}}</a>${{approved.has(d.slug+"/"+r.s)?'<span class="ap mono">Coriumist Approved</span>':''}}</li>`).join("")}}</ul></div>`}}
function show(d,scroll){{cities.classed("sel",c=>c.slug===d.slug);panel.style.display="block";
 panel.innerHTML=`<div class="ph"><div><div class="mono">${{ST[d.state]}}. Score ${{d.score}}. ${{"●".repeat(d.rings)}}</div><h3><a href="/circuit/${{d.slug}}/">${{d.name}}</a></h3></div><a class="mono" href="/circuit/${{d.slug}}/">The city page</a></div><p class="pnote">${{d.note}}</p><div class="rooms3">${{col(d,"hotel","Hotels")}}${{col(d,"restaurant","Restaurants")}}${{col(d,"attraction","Attractions and nightlife")}}</div>`;
 if(scroll)panel.scrollIntoView({{behavior:"smooth",block:"nearest"}})}}
cities.on("click",(e,d)=>show(d,true));
document.querySelectorAll("#mfilter button").forEach(b=>b.onclick=()=>{{document.querySelectorAll("#mfilter button").forEach(x=>x.classList.remove("on"));b.classList.add("on");const f=b.dataset.f;
 cities.classed("dim",d=>f==="all"?false:f==="active"?!(d.state==="open"||d.state==="opening"):d.tier!==+f)}});
show(read.cities[0],false);
}})();
</script>"""
MAP_HTML = f"""<div class="mono" id="mfilter" style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:14px"><button data-f="all" class="on">All forty</button><button data-f="active">Open and opening</button><button data-f="1">Permanent capitals</button><button data-f="2">Seasonal</button></div>
<svg id="map" viewBox="0 0 1180 560" style="width:100%;height:auto;display:block" aria-label="The circuit, forty cities at today's weight"></svg>
<div id="panel"></div>
<p class="disc mono">{DISCLAIMER}</p><style>{MAP_CSS}</style>{MAP_JS}"""

map_body = f"""
<div class="lede"><div><h2 class="big">The map.</h2><p class="dek">Forty cities at today's weight. Tap a mark for the read and the rooms: five hotels, five restaurants, five places to be after dark.</p></div>
<aside class="circuit"><div class="mono">Read date</div><div class="path"><span style="display:block;font-size:24px">{esc(date_long(TODAY))}</span></div></aside></div>
<section style="padding-top:0">{MAP_HTML}</section>"""
write("map/index.html", shell("The Map. The Coriumist", map_body, "/map/"))

# ----------------------------------------------------------------- sitemap + robots
urls = ["/", "/circuit/", "/places/", "/the-games/", "/index/", "/map/", "/methodology/", "/latest/"] + [f"/circuit/{c['slug']}/" for c in DATA["cities"]] + [f"/places/{c['slug']}/{v['slug']}/" for c in DATA["cities"] for v in c["venues"]]
write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>https://coriumist.com{u}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>" for u in urls) + "</urlset>")
write("robots.txt", "User-agent: *\nAllow: /\nSitemap: https://coriumist.com/sitemap.xml\n")
print(f"built {len(urls)} urls. top: " + ", ".join(f"{r['name']} {r['score']} {r['state']}" for r in reads[:6]))
print("wire:", [(w['name'], w['was'], w['state']) for w in wire[:6]])

# ----------------------------------------------------------------- home
# The hero is the one from the first site: full screen wordmark, a drifting halftone lens that inverts
# what passes through it, grain, ticker. Three scroll movements before the content starts.
HOME_CSS = """
:root{--soft:rgba(47,93,63,.62);--line:rgba(47,93,63,.32);--line-faint:rgba(47,93,63,.16);--pad:clamp(1.2rem,4vw,3.4rem)}
body.home{overflow-x:hidden}
.grain{position:fixed;inset:0;z-index:60;pointer-events:none;opacity:.05;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)'/%3E%3C/svg%3E")}
.hnav{position:fixed;top:0;left:0;right:0;z-index:50;height:3rem;display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:0 var(--pad);background:rgba(247,243,233,.88);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border-bottom:1px solid var(--line-faint)}
.hnav .brand{display:flex;align-items:center;gap:.65rem}.hnav .brand img{width:22px;height:25px}
.hnav .wordmark{font-family:"Space Mono",monospace;font-size:.72rem;letter-spacing:.28em;font-weight:700;text-transform:uppercase}
.hnav .links{display:flex;gap:1.5rem}.hnav .links a{font-family:"Space Mono",monospace;font-size:.62rem;letter-spacing:.18em;text-transform:uppercase;color:var(--soft);transition:color .25s}.hnav .links a:hover{color:var(--ink);text-decoration:none}
.hnav .links a.door{color:var(--ink);border:1px solid var(--line);padding:.45em .9em;border-radius:999px}.hnav .links a.door:hover{background:var(--ink);color:var(--paper)}
.ticker{position:fixed;top:calc(3rem + 1px);left:0;right:0;z-index:49;overflow:hidden;border-bottom:1px solid var(--line-faint);background:rgba(247,243,233,.88);backdrop-filter:blur(8px);padding:.42rem 0}
.ticker-track{display:flex;width:max-content;animation:tick 60s linear infinite}
.ticker span{font-family:"Space Mono",monospace;font-size:.6rem;letter-spacing:.18em;text-transform:uppercase;color:var(--soft);white-space:nowrap;padding-right:3.2rem}.ticker span::after{content:"·";padding-left:3.2rem;color:var(--line)}
@keyframes tick{to{transform:translateX(-50%)}}
.hero{position:relative;height:100svh;min-height:640px;overflow:hidden}
.hero-stage{position:absolute;left:50%;top:50%;width:100vw;height:100svh;min-height:640px;transform:translate(-50%,-50%);display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 var(--pad)}
.hero-eyebrow{margin-bottom:clamp(1rem,3vh,2rem);color:var(--soft)}
.mark-hero{width:clamp(76px,11vmin,120px);aspect-ratio:498/560;margin:0 auto clamp(1.1rem,2.6vh,1.9rem);background:center/contain no-repeat url(/assets/mark-green.webp)}
.mark-hero.cream{background-image:url(/assets/mark-cream.webp)}
.hero-the{font-family:"Space Mono",monospace;font-size:clamp(.7rem,1.6vw,1rem);letter-spacing:.9em;text-indent:.9em;margin-bottom:.4em;color:var(--ink)}
.hero-title{font-family:"Fraunces",serif;font-variation-settings:"opsz" 144,"wght" 520;font-size:clamp(3.4rem,14.5vw,14rem);line-height:.88;letter-spacing:-.03em;text-transform:uppercase;color:var(--ink)}
.hero-deck{margin-top:clamp(1.4rem,3.5vh,2.6rem);font-size:clamp(1.05rem,2.2vw,1.5rem);font-style:italic;font-variation-settings:"opsz" 40,"wght" 400;color:var(--ink)}
.hero-sub{margin-top:1.1rem;color:var(--soft)}
.hero-cue{position:absolute;bottom:1.6rem;left:50%;transform:translateX(-50%);color:var(--soft)}
.orb{position:absolute;left:50%;top:50%;width:clamp(280px,58vmin,640px);height:clamp(280px,58vmin,640px);border-radius:50%;overflow:hidden;z-index:2;background-color:var(--ink);background-image:radial-gradient(circle at 32% 28%,rgba(247,243,233,.14),transparent 55%),radial-gradient(var(--paper) 1px,transparent 1.45px);background-size:100% 100%,6px 6px;box-shadow:0 0 0 1px var(--line-faint);transform:translate(-50%,-50%) translate(-16vmin,3vmin);animation:drift 26s ease-in-out infinite alternate}
.orb-stage{position:absolute;left:50%;top:50%;width:100vw;height:100svh;min-height:640px;transform:translate(-50%,-50%) translate(16vmin,-3vmin);animation:drift-inv 26s ease-in-out infinite alternate;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 var(--pad)}
.orb-stage .hero-eyebrow,.orb-stage .hero-sub{color:rgba(247,243,233,.78)}.orb-stage .hero-the,.orb-stage .hero-title,.orb-stage .hero-deck{color:var(--paper)}
@keyframes drift{to{transform:translate(-50%,-50%) translate(16vmin,-3vmin)}}@keyframes drift-inv{to{transform:translate(-50%,-50%) translate(-16vmin,3vmin)}}
.mv{position:relative;min-height:100svh;display:flex;flex-direction:column;justify-content:center;padding:clamp(5rem,12vh,9rem) var(--pad);border-top:1px solid var(--line-faint);overflow:hidden}
.mv .eyebrow{display:flex;align-items:baseline;gap:1rem;margin-bottom:clamp(2rem,6vh,3.6rem);color:var(--soft)}.mv .eyebrow::after{content:"";flex:1;height:1px;background:var(--line-faint);transform:translateY(-.35em)}
.mv .h2{font-family:"Fraunces",serif;font-variation-settings:"opsz" 72,"wght" 420;font-size:clamp(2rem,5.4vw,4.2rem);line-height:1.04;letter-spacing:-.015em;max-width:22ch}
.mv .body{margin-top:2.2rem;font-size:clamp(1.05rem,1.7vw,1.25rem);max-width:52ch}.mv .aside{margin-top:2.6rem;color:var(--soft);font-style:italic;font-variation-settings:"opsz" 30,"wght" 400}
.ghost{position:absolute;pointer-events:none;background:center/contain no-repeat url(/assets/mark-green.webp);width:min(540px,64vw);aspect-ratio:498/560;right:-9%;top:50%;transform:translateY(-50%) rotate(9deg);opacity:.055}
.stops{list-style:none;margin-top:1rem;max-width:56rem}.stop{display:grid;grid-template-columns:2.6rem 1fr auto;gap:1.2rem;align-items:baseline;padding:1.05rem 0;border-bottom:1px solid var(--line-faint);opacity:.35;transition:opacity .6s}
.stop.lit{opacity:1}.stop .dot{width:8px;height:8px;border-radius:50%;border:1px solid var(--ink);position:relative;top:-2px}.stop.lit .dot{background:var(--ink)}
.stop .c{font-family:"Fraunces",serif;font-variation-settings:"opsz" 40,"wght" 460;font-size:clamp(1.3rem,2.6vw,1.9rem)}.stop .s{font-family:"Space Mono",monospace;font-size:.62rem;letter-spacing:.18em;text-transform:uppercase;color:var(--soft)}
.stop .m{display:block;margin-top:.3rem;color:var(--soft);font-size:.98rem;max-width:60ch}
[data-reveal]{opacity:0;transform:translateY(26px);transition:opacity .9s cubic-bezier(.22,1,.36,1),transform .9s cubic-bezier(.22,1,.36,1)}[data-reveal].in{opacity:1;transform:none}
.content{padding:clamp(4rem,9vh,7rem) var(--pad);border-top:1px solid var(--line-faint)}.content .eyebrow{display:flex;align-items:baseline;gap:1rem;margin-bottom:2.2rem;color:var(--soft)}.content .eyebrow::after{content:"";flex:1;height:1px;background:var(--line-faint);transform:translateY(-.35em)}
.dgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:0;border-top:1px solid var(--line)}
.dgrid article{padding:1.4rem 1.4rem 1.6rem 0;border-bottom:1px solid var(--line-faint);border-right:1px solid var(--line-faint);min-height:14rem;display:flex;flex-direction:column}
.dgrid article:nth-child(3n){border-right:0;padding-right:0}.dgrid article:nth-child(3n+2),.dgrid article:nth-child(3n){padding-left:1.4rem}
.dgrid .k{color:var(--soft);display:flex;justify-content:space-between;gap:8px}.dgrid h4{font-family:"Fraunces",serif;font-variation-settings:"opsz" 72,"wght" 460;font-size:clamp(1.25rem,2vw,1.6rem);line-height:1.12;letter-spacing:-.01em;margin:.9rem 0 .7rem}
.dgrid p{color:var(--ink);font-size:.98rem;line-height:1.5;flex:1}.dgrid .go{margin-top:1rem;color:var(--soft)}
.viewall{display:flex;justify-content:center;margin-top:2.2rem}.viewall button{background:transparent;border:1px solid var(--line);color:var(--ink);font-family:"Space Mono",monospace;font-size:.66rem;letter-spacing:.24em;text-transform:uppercase;padding:1rem 2.2rem;cursor:pointer;border-radius:999px;transition:background .3s,color .3s}.viewall button:hover{background:var(--ink);color:var(--paper)}
.doorblk{background:var(--ink);color:var(--paper);padding:clamp(5rem,12vh,9rem) var(--pad);text-align:center;position:relative;overflow:hidden}
.doorblk .ghost{background-image:url(/assets/mark-cream.webp);width:min(620px,78vw);right:-16%;transform:translateY(-50%) rotate(-7deg);opacity:.07}
.doorblk h3{font-family:"Fraunces",serif;font-variation-settings:"opsz" 90,"wght" 440;font-size:clamp(2.2rem,6.5vw,4.4rem);line-height:1.02;letter-spacing:-.02em;color:var(--paper);position:relative}
.doorblk p{margin:1.6rem auto 0;font-style:italic;font-variation-settings:"opsz" 30,"wght" 400;color:rgba(247,243,233,.82);max-width:38ch;position:relative}
.doorblk form{margin:3rem auto 0;max-width:30rem;display:flex;border-bottom:1px solid rgba(247,243,233,.4);position:relative}.doorblk input{flex:1;background:transparent;border:0;padding:.7rem 0;color:var(--paper);font-family:"Space Mono",monospace;font-size:.85rem;letter-spacing:.08em}.doorblk input::placeholder{color:rgba(247,243,233,.4)}
.doorblk button{background:transparent;border:0;color:var(--paper);font-family:"Space Mono",monospace;font-size:.66rem;letter-spacing:.24em;text-transform:uppercase;cursor:pointer;padding:.7rem 0 .7rem 1rem}
@media (max-width:900px){.hnav .links a:not(.door){display:none}.dgrid{grid-template-columns:1fr}.dgrid article{border-right:0;padding-left:0!important;padding-right:0}.stop{grid-template-columns:1.6rem 1fr;gap:.8rem}.stop .s{grid-column:2}}
@media (prefers-reduced-motion:reduce){.ticker-track,.orb,.orb-stage{animation:none}[data-reveal]{opacity:1;transform:none;transition:none}}
"""
stops_html = "".join(f'<li class="stop{" lit" if i==0 else ""}" data-stop><span class="dot"></span><span><span class="c"><a href="/circuit/{r["slug"]}/">{esc(r["name"])}</a></span><span class="m">{esc(r["note"])}</span></span><span class="s">{STATE_WORD[r["state"]]} · {r["score"]}</span></li>' for i, r in enumerate(reads[:6]))
ticker_lines = [w["note"] for w in wire[:6]] or [r["note"] for r in reads[:6]]
ticker_html = "".join(f"<span>{esc(t)}</span>" for t in ticker_lines * 2)

home_body = f"""
<div class="grain" aria-hidden="true"></div>
<nav class="hnav"><a class="brand" href="/"><img src="/assets/mark-green.webp" alt=""><span class="wordmark">The Coriumist</span></a>
<div class="links"><a href="#dispatches">Dispatches</a><a href="#map">The map</a><a href="/circuit/">Circuit</a><a href="/index/">Index</a><a href="/the-games/">The Games</a><a class="door" href="#door">The Door</a></div></nav>
<div class="ticker" aria-hidden="true"><div class="ticker-track">{ticker_html}</div></div>

<header class="hero" id="top">
 <div class="hero-stage"><p class="hero-eyebrow mono">A private intelligence publication</p><div class="mark-hero" role="img" aria-label="The Coriumist contour mark"></div><p class="hero-the">The</p><h1 class="hero-title">Coriumist</h1><p class="hero-deck">Where capital congregates.</p><p class="hero-sub mono">Public record, read closely &nbsp;·&nbsp; est. MMXXVI</p></div>
 <div class="orb" aria-hidden="true"><div class="orb-stage"><p class="hero-eyebrow mono">A private intelligence publication</p><div class="mark-hero cream"></div><p class="hero-the">The</p><p class="hero-title">Coriumist</p><p class="hero-deck">Where capital congregates.</p><p class="hero-sub mono">Public record, read closely &nbsp;·&nbsp; est. MMXXVI</p></div></div>
 <p class="hero-cue mono">Scroll · 01</p>
</header>

<section class="mv" id="premise"><div class="ghost" aria-hidden="true"></div><p class="eyebrow mono">01 · The premise</p>
 <h2 class="h2" data-reveal>Capital clusters. By season, by coordinate, by invitation.</h2>
 <p class="body" data-reveal>The Coriumist reads the public record of the clustering. Flight corridors, filings, rosters, permits, notices of race. Coordinates, not people. Cities, not addresses.</p>
 <p class="aside" data-reveal>Inference is marked as inference. Everything else is silence.</p></section>

<section class="mv" id="circuit"><p class="eyebrow mono">02 · The circuit, read {esc(TODAY.strftime('%-d %B'))}</p>
 <h2 class="h2" data-reveal>Six places carrying the weight this week.</h2>
 <ul class="stops" data-reveal>{stops_html}</ul>
 <p class="aside" data-reveal><a href="/index/">All forty, ranked</a></p></section>

<section class="content" id="dispatches"><p class="eyebrow mono">03 · Dispatches</p>
 <div class="dgrid" id="dgrid"></div>
 <div class="viewall"><button id="viewall" type="button">View all dispatches</button></div></section>

<section class="content" id="map" style="padding-top:clamp(3rem,7vh,5rem)"><p class="eyebrow mono">04 · The map</p>
 {MAP_HTML}</section>

<section class="doorblk" id="door"><div class="ghost" aria-hidden="true"></div><h3>The door is currently closed.</h3><p>Leave an address. When the door opens, it opens in order of arrival.</p>
 <form action="https://formspree.io/f/REPLACE_WITH_FORM_ID" method="POST"><input type="email" name="email" placeholder="Email" required aria-label="Email"><button type="submit">Enter</button></form></section>
{SB_JS}
<script>
(async()=>{{
 const strip=b=>(b||"").replace(/<[^>]+>/g," ").replace(/\\s+/g," ").trim();
 const card=r=>`<article><div class="k mono"><span>${{r.format||"Dispatch"}}</span><span>${{fmtDate(r.publish_at)}}</span></div><h4><a href="/read/?id=${{r.id}}">${{r.title}}</a></h4><p>${{strip(r.body).slice(0,170)}}</p><a class="go mono" href="/read/?id=${{r.id}}">Read</a></article>`;
 const grid=document.getElementById("dgrid");
 const rows=await sb("content?status=eq.published&select=id,format,title,body,publish_at&order=publish_at.desc&limit=12");
 grid.innerHTML=rows.length?rows.map(card).join(""):'<article><div class="k mono"><span>Dispatch</span></div><h4>Filed when it is filed.</h4><p>The first pieces publish through the article pipeline and appear here.</p></article>';
 document.getElementById("viewall").onclick=async e=>{{e.target.disabled=true;e.target.textContent="Loading";const all=await sb("content?status=eq.published&select=id,format,title,body,publish_at&order=publish_at.desc&limit=200");grid.innerHTML=all.map(card).join("");e.target.parentElement.innerHTML='<a class="mono" href="/latest/">Everything, in order</a>'}};
 const io=new IntersectionObserver(es=>es.forEach(en=>{{if(en.isIntersecting){{en.target.classList.add("in");io.unobserve(en.target)}}}}),{{threshold:.12}});
 document.querySelectorAll("[data-reveal]").forEach(el=>io.observe(el));
 const stops=[...document.querySelectorAll("[data-stop]")];let k=0;setInterval(()=>{{stops.forEach(s=>s.classList.remove("lit"));k=(k+1)%stops.length;stops[k].classList.add("lit")}},2600);
}})();
</script>"""

home_page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Coriumist</title><meta name="description" content="Where capital congregates. By season, by coordinate. Public record only.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,480;9..144,520&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>{CSS}{HOME_CSS}</style></head>
<body class="home">{home_body}
<footer><div class="wrap">
<div class="foot mono">
<div><h5>The circuit</h5><ul><li><a href="/circuit/">Cities</a></li><li><a href="/map/">Map</a></li><li><a href="/index/">The Index</a></li><li><a href="/places/">Places</a></li></ul></div>
<div><h5>The desk</h5><ul><li><a href="/latest/">Dispatches</a></li><li><a href="/the-games/">The Games</a></li></ul></div>
<div><h5>The data</h5><ul><li><a href="/methodology/">Methodology</a></li><li><a href="/data/read.json">Today's read (JSON)</a></li></ul></div>
<div><h5>The Coriumist</h5><ul><li><a href="mailto:coriumist.ops@gmail.com">Contact</a></li><li><a href="https://www.instagram.com/coriumist">Instagram</a></li></ul></div>
</div>
<div class="sign"><span class="line">Money moves. We map it.</span><span class="mono">Public sources. City level. Never an address. The Coriumist, {TODAY.year}.</span></div>
</div></footer></body></html>"""
write("index.html", home_page)
