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
json.dump({"date": TODAY.isoformat(), "cities": reads, "wire": wire[:12], "disclaimer": DISCLAIMER}, open(prev_path, "w"), indent=1, ensure_ascii=False)

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
 .foot,.dir{grid-template-columns:1fr 1fr}.mast h1{font-size:34px}.sign{flex-direction:column;align-items:flex-start;gap:12px}.venues{columns:1}
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

# ----------------------------------------------------------------- home
cities_by_slug = {c["slug"]: c for c in DATA["cities"]}
top = reads[:5]
flat = [r for r in reads if r["state"] == "flat"][:1]
path_html = "".join(f'<a href="/circuit/{r["slug"]}/">{esc(r["name"])}<span class="st">{STATE_WORD[r["state"]]}</span></a>' for r in top)
path_html += "".join(f'<a class="faint" href="/circuit/{r["slug"]}/">{esc(r["name"])}<span class="st">flat</span></a>' for r in flat)
wire_html = "".join(f'<article><div class="tag mono"><span>{STATE_WORD[w["state"]]}</span><a href="/circuit/{w["slug"]}/">{esc(w["name"])}</a></div><p>{esc(w["note"])}</p></article>' for w in wire[:6])

home = f"""
<div class="lede"><div><h2 class="big">This week, on the circuit.</h2><p class="dek">Where capital is moving, where it is gathering, and what happens to a place when it arrives.</p></div>
<aside class="circuit"><div class="mono">The circuit, read {esc(TODAY.strftime('%-d %B'))}</div><div class="path">{path_html}</div><p class="mono" style="margin-top:16px;color:var(--mute)"><a href="/index/">Full ranking, forty cities</a></p></aside></div>

<section id="wire"><div class="sec-head"><h3 class="mono">On the wire</h3><span class="mono">State changes. Recomputed daily.</span></div><div class="wire">{wire_html}</div></section>

<section id="dispatch"><div class="sec-head"><h3 class="mono">The current dispatch</h3><span class="mono" id="d-date"></span></div>
<div class="feature"><div><div class="mono" id="d-kicker">Dispatch</div><h3 id="d-title">Filed when it is filed.</h3><p class="standfirst" id="d-body"></p><a class="read mono" id="d-link" href="/latest/">Read the dispatch</a></div>
<div class="facts"><dl>
<div><dt class="mono">Cities read today</dt><dd>{len(reads)}</dd></div><div><dt class="mono">Rooms mapped</dt><dd>{sum(len(c['venues']) for c in DATA['cities'])}</dd></div>
<div><dt class="mono">Open</dt><dd>{sum(1 for r in reads if r['state']=='open')}</dd></div><div><dt class="mono">Opening</dt><dd>{sum(1 for r in reads if r['state']=='opening')}</dd></div>
<div><dt class="mono">Closing or dispersing</dt><dd>{sum(1 for r in reads if r['state'] in ('closing','dispersing'))}</dd></div><div><dt class="mono">Permanent capitals flat</dt><dd>{sum(1 for r in reads if r['state']=='flat')}</dd></div>
</dl><p class="disc mono">{DISCLAIMER}</p></div></div></section>

<section id="games"><div class="sec-head"><h3 class="mono">The Games</h3><a class="mono" href="/the-games/">The section</a></div><div class="filed" id="games-list"><p class="mono" style="color:var(--mute)">Nothing filed under The Games yet.</p></div></section>

<section id="filed" class="filed"><div class="sec-head"><h3 class="mono">Filed recently</h3><a class="mono" href="/latest/">Everything</a></div><div id="filed-list"></div></section>

<section id="gate" class="gate"><div><h3>The door is currently closed.</h3><p>Leave an address. When the door opens, it opens in order of arrival.</p></div>
<form action="https://formspree.io/f/REPLACE_WITH_FORM_ID" method="POST"><input type="email" name="email" placeholder="Email" required aria-label="Email"><button type="submit" class="mono">Enter</button></form></section>
{SB_JS}
<script>
(async()=>{{
 const rows=await sb("content?status=eq.published&select=id,format,title,body,publish_at&order=publish_at.desc&limit=12");
 const strip=b=>(b||"").replace(/<[^>]+>/g," ").replace(/\\s+/g," ").trim();
 const disp=rows.find(r=>/dispatch/i.test(r.format||""))||rows[0];
 if(disp){{document.getElementById("d-kicker").textContent=(disp.format||"Dispatch")+". "+fmtDate(disp.publish_at);document.getElementById("d-title").textContent=disp.title;document.getElementById("d-body").textContent=strip(disp.body).slice(0,220);document.getElementById("d-link").href="/read/?id="+disp.id;document.getElementById("d-date").textContent="Filed "+fmtDate(disp.publish_at)}}
 const item=r=>`<article><div class="meta mono">${{r.format||""}}<br>${{fmtDate(r.publish_at)}}</div><div><h4><a href="/read/?id=${{r.id}}">${{r.title}}</a></h4><p>${{strip(r.body).slice(0,180)}}</p></div><div class="place mono"></div></article>`;
 const games=rows.filter(r=>/game/i.test(r.format||""));
 if(games.length)document.getElementById("games-list").innerHTML=games.slice(0,3).map(item).join("");
 document.getElementById("filed-list").innerHTML=rows.slice(0,6).map(item).join("");
}})();
</script>"""
write("index.html", shell("The Coriumist", home, "/"))

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
    ven = "".join(f'<li><a href="/places/{c["slug"]}/{v["slug"]}/">{esc(v["name"])}</a><span class="k mono" data-v="{c["slug"]}/{v["slug"]}"></span></li>' for v in c["venues"])
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
<section><div class="sec-head"><h3 class="mono">The rooms</h3><span class="mono">Public venues. Coriumist Approved where designated.</span></div><ul class="venues">{ven}</ul></section>
<section><div class="sec-head"><h3 class="mono">The windows</h3></div><div class="facts"><dl>{windows}</dl></div><p class="disc mono">{DISCLAIMER}</p></section>
{SB_JS}<script>(async()=>{{const v=await sb("venues?city_slug=eq.{c["slug"]}&approved=eq.true&select=slug");const s=new Set(v.map(x=>x.slug));document.querySelectorAll("[data-v]").forEach(e=>{{if(s.has(e.dataset.v.split("/")[1]))e.textContent="Coriumist Approved"}})}})();</script>"""
    write(f"circuit/{c['slug']}/index.html", shell(f"{c['name']}. The Coriumist Circuit", body, "/circuit/", desc=c["why"]))

# ----------------------------------------------------------------- places
pl = "".join(f'<section><div class="sec-head"><h3 class="mono"><a href="/circuit/{c["slug"]}/">{esc(c["name"])}</a></h3><span class="mono">{len(c["venues"])} rooms</span></div><ul class="venues">' + "".join(f'<li><a href="/places/{c["slug"]}/{v["slug"]}/">{esc(v["name"])}</a></li>' for v in c["venues"]) + "</ul></section>" for c in sorted(DATA["cities"], key=lambda c: (c["tier"], c["name"])))
write("places/index.html", shell("Places. The rooms on the circuit", f'<div class="lede"><div><h2 class="big">The rooms.</h2><p class="dek">One hundred and seventy nine public venues where the circuit actually sits. Hotels, clubs, restaurants, beach clubs, marinas. The designation is ours. The address is theirs.</p></div></div>{pl}', "/places/"))

for c in DATA["cities"]:
    for v in c["venues"]:
        body = f"""
<p class="crumb mono"><a href="/places/">Places</a> / <a href="/circuit/{c["slug"]}/">{esc(c["name"])}</a> / {esc(v["name"])}</p>
<div class="lede"><div><div class="mono" id="v-status">On the map. Designation pending.</div><h2 class="big">{esc(v["name"])}</h2><p class="dek" id="v-what">{esc(c["name"])}. {esc(c["why"])}</p></div>
<aside class="circuit"><div class="facts"><dl>
<div><dt class="mono">City</dt><dd><a href="/circuit/{c["slug"]}/">{esc(c["name"])}</a></dd></div><div><dt class="mono">Kind</dt><dd id="v-kind">Room</dd></div>
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

# ----------------------------------------------------------------- map
map_body = f"""
<div class="lede"><div><h2 class="big">The map.</h2><p class="dek">Forty cities at today's weight. Tap a mark for the read and the rooms.</p></div>
<aside class="circuit"><div class="mono">Read date</div><div class="path"><span style="display:block;font-size:24px">{esc(date_long(TODAY))}</span></div>
<div class="mono" id="mfilter" style="margin-top:14px;display:flex;gap:14px;flex-wrap:wrap"><button data-f="all" class="on">All</button><button data-f="active">Open and opening</button><button data-f="1">Permanent</button></div></aside></div>
<section style="padding-top:0"><div id="mapwrap" style="position:relative"><svg id="map" viewBox="0 0 1180 560" style="width:100%;height:auto;display:block"></svg>
<div id="panel" class="facts" style="display:none;margin-top:18px"><dl id="pdl"></dl><p id="pnote" class="dek" style="margin:14px 0 0;font-size:18px"></p><p id="prooms" class="mono" style="margin-top:12px;line-height:1.9"></p></div></div>
<p class="disc mono">{DISCLAIMER}</p></section>
<style>
#mfilter button{{border:0;background:transparent;color:var(--mute);font:inherit;cursor:pointer;padding:0;border-bottom:1px solid transparent}}#mfilter button.on{{color:var(--ink);border-bottom-color:var(--ink)}}
.land{{fill:none;stroke:rgba(47,93,63,.35);stroke-width:.6}}.gr{{fill:none;stroke:rgba(47,93,63,.12);stroke-width:.5}}
.city{{cursor:pointer}}.city circle{{fill:none;stroke:#2f5d3f;stroke-width:1.1}}.city circle.core{{fill:#2f5d3f}}.city.dim{{opacity:.18}}.city.sel circle{{stroke-width:1.8}}
.city text{{font-family:"Space Mono",monospace;font-size:9px;fill:#2f5d3f;letter-spacing:.04em}}
</style>
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
cities.each(function(d){{const s=d3.select(this);for(let i=0;i<d.rings;i++)s.append("circle").attr("r",2.2+i*2.6);s.append("circle").attr("class","core").attr("r",1.6);
 if(d.rings>=4)s.append("text").attr("x",d.rings*2.6+6).attr("y",3).text(d.name)}});
const panel=document.getElementById("panel");
function show(d){{cities.classed("sel",c=>c.slug===d.slug);panel.style.display="block";
 document.getElementById("pdl").innerHTML=[["City",`<a href="/circuit/${{d.slug}}/">${{d.name}}</a>`],["State",ST[d.state]],["Score",d.score],["Rings","●".repeat(d.rings)]].map(x=>`<div><dt class="mono">${{x[0]}}</dt><dd>${{x[1]}}</dd></div>`).join("");
 document.getElementById("pnote").textContent=d.note;
 fetch("/circuit/"+d.slug+"/").then(r=>r.text()).then(t=>{{const m=[...t.matchAll(/<li><a href="(\\/places\\/[^"]+)">([^<]+)<\\/a>/g)];document.getElementById("prooms").innerHTML=m.map(x=>`<a href="${{x[1]}}">${{x[2]}}</a>`).join("  ·  ")}});
 panel.scrollIntoView({{behavior:"smooth",block:"nearest"}})}}
cities.on("click",(e,d)=>show(d));
document.querySelectorAll("#mfilter button").forEach(b=>b.onclick=()=>{{document.querySelectorAll("#mfilter button").forEach(x=>x.classList.remove("on"));b.classList.add("on");const f=b.dataset.f;
 cities.classed("dim",d=>f==="all"?false:f==="active"?!(d.state==="open"||d.state==="opening"):d.tier!==+f)}});
show(read.cities[0]);
}})();
</script>"""
write("map/index.html", shell("The Map. The Coriumist", map_body, "/map/"))

# ----------------------------------------------------------------- sitemap + robots
urls = ["/", "/circuit/", "/places/", "/the-games/", "/index/", "/map/", "/methodology/", "/latest/"] + [f"/circuit/{c['slug']}/" for c in DATA["cities"]] + [f"/places/{c['slug']}/{v['slug']}/" for c in DATA["cities"] for v in c["venues"]]
write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>https://coriumist.com{u}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>" for u in urls) + "</urlset>")
write("robots.txt", "User-agent: *\nAllow: /\nSitemap: https://coriumist.com/sitemap.xml\n")
print(f"built {len(urls)} urls. top: " + ", ".join(f"{r['name']} {r['score']} {r['state']}" for r in reads[:6]))
print("wire:", [(w['name'], w['was'], w['state']) for w in wire[:6]])
