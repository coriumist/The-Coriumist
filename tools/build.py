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
try: PHOTOS = json.load(open(os.path.join(ROOT, "data", "photos.json")))
except Exception: PHOTOS = {}
def photos(slug): return [p for p in PHOTOS.get(slug, []) if p.get("url")]
def hero(slug):
    p = photos(slug); return p[0] if p else None
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
for r in reads:
    r["photos"] = [{"url": p["url"], "credit": p.get("credit", ""), "license": p.get("license", ""), "page": p.get("page", "")} for p in photos(r["slug"])][:6]
json.dump({"date": TODAY.isoformat(), "cities": reads, "wire": wire[:12], "rooms": rooms, "disclaimer": DISCLAIMER}, open(prev_path, "w"), indent=1, ensure_ascii=False)


# ----------------------------------------------------------------- shell
def esc(s): return html.escape(str(s), quote=True)
def date_long(d): return d.strftime("%A %-d %B %Y")
STATE_WORD = {"opening": "Opening", "open": "Open", "closing": "Closing", "dispersing": "Dispersing", "flat": "Flat", "quiet": "Quiet"}
TIER_WORD = {1: "Permanent capital", 2: "Seasonal capital", 3: "Floating capital"}
KIND_WORD = {"hotel": "Hotels", "restaurant": "Restaurants", "attraction": "Attractions and nightlife"}
cities_by_slug = {c["slug"]: c for c in DATA["cities"]}
reads_by_slug = {r["slug"]: r for r in reads}
FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,480;9..144,520&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">'
LEAFLET = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"><script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>'

# The dark system. Deep forest ground, cream ink, the green as accent and as the tint that sits behind every photograph.
CSS = """
:root{--bg:#0b1710;--bg2:#10231a;--bg3:#16302300;--ink:#f7f3e9;--green:#2f5d3f;--accent:#7fbf98;--soft:rgba(247,243,233,.62);--mute:rgba(247,243,233,.45);--line:rgba(247,243,233,.16);--line2:rgba(247,243,233,.08);--pad:clamp(1.2rem,4vw,3.4rem);--w:1280px}
*{box-sizing:border-box;margin:0;padding:0}
html{background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased;scroll-behavior:smooth}
body{font-family:"Fraunces",Georgia,serif;font-variation-settings:"opsz" 18,"wght" 400;font-size:17px;line-height:1.55;overflow-x:hidden}
a{color:inherit;text-decoration:none}a:hover{text-decoration:underline;text-underline-offset:3px;text-decoration-thickness:1px}
a:focus-visible,button:focus-visible,input:focus-visible{outline:1.5px solid var(--accent);outline-offset:3px}
img{display:block;max-width:100%}
.mono{font-family:"Space Mono",ui-monospace,monospace;font-size:11px;letter-spacing:.08em;line-height:1.5;text-transform:uppercase}
.wrap{max-width:var(--w);margin:0 auto;padding:0 var(--pad)}
.grain{position:fixed;inset:0;z-index:60;pointer-events:none;opacity:.06;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='160'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2'/%3E%3C/filter%3E%3Crect width='160' height='160' filter='url(%23n)'/%3E%3C/svg%3E")}
.hnav{position:fixed;top:0;left:0;right:0;z-index:50;height:3.2rem;display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:0 var(--pad);background:rgba(11,23,16,.72);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid var(--line2)}
.hnav .brand{display:flex;align-items:center;gap:.65rem}.hnav .brand img{width:22px;height:25px}
.hnav .wordmark{font-family:"Space Mono",monospace;font-size:.72rem;letter-spacing:.28em;font-weight:700;text-transform:uppercase}
.hnav .links{display:flex;gap:1.5rem}.hnav .links a{font-family:"Space Mono",monospace;font-size:.62rem;letter-spacing:.18em;text-transform:uppercase;color:var(--soft);transition:color .25s}.hnav .links a:hover{color:var(--ink);text-decoration:none}
.hnav .links a.door{color:var(--ink);border:1px solid var(--line);padding:.45em .9em;border-radius:999px}.hnav .links a.door:hover{background:var(--ink);color:var(--bg)}
.hnav .menu{display:none;background:transparent;border:1px solid var(--line);color:var(--ink);padding:.45em .9em;border-radius:999px;cursor:pointer}
.sheet{display:none;position:fixed;inset:3.2rem 0 0 0;z-index:48;background:rgba(11,23,16,.97);padding:2rem var(--pad);flex-direction:column;gap:1.1rem}
.sheet a{font-family:"Fraunces",serif;font-variation-settings:"opsz" 72,"wght" 460;font-size:2rem;line-height:1.1}
body.menu-open .sheet{display:flex}body.menu-open{overflow:hidden}
.ticker{position:fixed;top:calc(3.2rem + 1px);left:0;right:0;z-index:49;overflow:hidden;border-bottom:1px solid var(--line2);background:rgba(11,23,16,.72);backdrop-filter:blur(12px);padding:.42rem 0}
.ticker-track{display:flex;width:max-content;animation:tick 70s linear infinite}
.ticker span{font-family:"Space Mono",monospace;font-size:.6rem;letter-spacing:.18em;text-transform:uppercase;color:var(--soft);white-space:nowrap;padding-right:3.2rem}.ticker span::after{content:"·";padding-left:3.2rem;color:var(--line)}
@keyframes tick{to{transform:translateX(-50%)}}
main{padding-top:5.4rem}
.eyebrow{display:flex;align-items:baseline;gap:1rem;margin-bottom:1.6rem;color:var(--soft)}.eyebrow::after{content:"";flex:1;height:1px;background:var(--line2);transform:translateY(-.35em)}
h1.big,h2.big{font-variation-settings:"opsz" 144,"wght" 460;font-size:clamp(2.4rem,6vw,4.6rem);line-height:1.02;letter-spacing:-.018em;max-width:16ch}
.dek{margin-top:16px;font-size:clamp(1.05rem,1.6vw,1.3rem);line-height:1.45;max-width:44ch;color:var(--soft)}
section{padding:clamp(3.4rem,8vh,6rem) 0;border-top:1px solid var(--line2)}
/* photo layering: green tint layer, photograph on top, dark fade at the foot */
.ph{position:relative;overflow:hidden;background:var(--green);isolation:isolate}
.ph img{width:100%;height:100%;object-fit:cover;display:block;filter:saturate(.82) contrast(1.04);opacity:.92;transition:transform 1.6s cubic-bezier(.22,1,.36,1)}
.ph::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(47,93,63,.22) 0%,rgba(11,23,16,.12) 40%,rgba(11,23,16,.86) 100%);pointer-events:none}
.ph:hover img{transform:scale(1.04)}
.ph .cap{position:absolute;left:0;right:0;bottom:0;padding:1.1rem 1.2rem;z-index:2}
.credit{position:absolute;right:.9rem;bottom:.6rem;color:rgba(247,243,233,.42);font-size:9px;z-index:3;letter-spacing:.06em}
.hero{position:relative;height:100svh;min-height:640px;overflow:hidden;margin-top:-5.4rem}
.hero .bg{position:absolute;inset:0;background:var(--green)}
.hero .bg img{width:100%;height:100%;object-fit:cover;opacity:.55;filter:saturate(.8);animation:kb 28s ease-in-out infinite alternate;transform-origin:center}
.hero .bg::after{content:"";position:absolute;inset:0;background:radial-gradient(ellipse at center,rgba(11,23,16,.15) 0%,rgba(11,23,16,.72) 70%,rgba(11,23,16,.96) 100%),linear-gradient(180deg,rgba(47,93,63,.25),transparent 40%,var(--bg) 100%)}
@keyframes kb{from{transform:scale(1.02) translate(0,0)}to{transform:scale(1.12) translate(-1.5%,1%)}}
.hero-stage{position:relative;z-index:2;height:100%;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:0 var(--pad)}
.hero-eyebrow{margin-bottom:clamp(1rem,3vh,2rem);color:var(--soft)}
.mark-hero{width:clamp(76px,11vmin,120px);aspect-ratio:498/560;margin:0 auto clamp(1.1rem,2.6vh,1.9rem);background:center/contain no-repeat url(/assets/mark-cream.webp)}
.hero-the{font-family:"Space Mono",monospace;font-size:clamp(.7rem,1.6vw,1rem);letter-spacing:.9em;text-indent:.9em;margin-bottom:.4em;color:var(--accent)}
.hero-title{font-family:"Fraunces",serif;font-variation-settings:"opsz" 144,"wght" 520;font-size:clamp(3.4rem,14.5vw,14rem);line-height:.88;letter-spacing:-.03em;text-transform:uppercase;color:var(--ink)}
.hero-deck{margin-top:clamp(1.4rem,3.5vh,2.6rem);font-size:clamp(1.05rem,2.2vw,1.5rem);font-style:italic;font-variation-settings:"opsz" 40,"wght" 400}
.hero-sub{margin-top:1.1rem;color:var(--soft)}
.hero-cue{position:absolute;bottom:1.6rem;left:50%;transform:translateX(-50%);color:var(--soft);z-index:2}
.hero .where{position:absolute;left:var(--pad);bottom:1.6rem;z-index:2;color:var(--soft)}
[data-reveal]{opacity:0;transform:translateY(24px);transition:opacity .9s cubic-bezier(.22,1,.36,1),transform .9s cubic-bezier(.22,1,.36,1)}[data-reveal].in{opacity:1;transform:none}
/* horizontal rails */
.rail{display:flex;gap:18px;overflow-x:auto;scroll-snap-type:x mandatory;padding:4px var(--pad) 18px;margin:0 calc(-1 * var(--pad));scrollbar-width:thin;scrollbar-color:var(--line) transparent}
.rail>*{scroll-snap-align:start;flex:0 0 min(78vw,400px)}
.rail.wide>*{flex:0 0 min(84vw,560px)}
.card{position:relative;border-radius:4px;overflow:hidden;background:var(--bg2);border:1px solid var(--line2)}
.card .ph{aspect-ratio:4/5}.card.wide .ph{aspect-ratio:16/10}
.card .cap .k{color:var(--soft);display:flex;justify-content:space-between;gap:10px;margin-bottom:.5rem}
.card .cap h3{font-variation-settings:"opsz" 72,"wght" 460;font-size:clamp(1.3rem,2vw,1.7rem);line-height:1.1;letter-spacing:-.01em}
.card .cap p{margin-top:.5rem;color:var(--soft);font-size:.95rem;line-height:1.45;max-width:38ch}
.card .cap .st{margin-top:.7rem;color:var(--accent)}
.railhead{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:1.2rem}
.railhead .nav{display:flex;gap:8px}.railhead .nav button{background:transparent;border:1px solid var(--line);color:var(--ink);width:36px;height:36px;border-radius:50%;cursor:pointer;font:inherit}
.railhead .nav button:hover{background:var(--ink);color:var(--bg)}
.btn{display:inline-block;background:transparent;border:1px solid var(--line);color:var(--ink);font-family:"Space Mono",monospace;font-size:.66rem;letter-spacing:.24em;text-transform:uppercase;padding:.95rem 2rem;cursor:pointer;border-radius:999px;transition:background .3s,color .3s}.btn:hover{background:var(--ink);color:var(--bg);text-decoration:none}
/* gallery */
.gallery{display:grid;grid-template-columns:2fr 1fr 1fr;grid-auto-rows:220px;gap:10px}
.gallery .ph:first-child{grid-row:span 2}
.gallery .ph{border-radius:3px}
/* facts */
.facts{border-top:1px solid var(--line)}.facts dl{display:grid;grid-template-columns:1fr 1fr}
.facts div{padding:12px 0;border-bottom:1px solid var(--line2)}.facts div:nth-child(odd){padding-right:20px;border-right:1px solid var(--line2)}.facts div:nth-child(even){padding-left:20px}
.facts dt{color:var(--mute)}.facts dd{margin-top:5px;font-size:17px;line-height:1.35}
.disc{color:var(--mute);padding-top:14px;font-size:10px;text-transform:none;letter-spacing:.04em}
.two{display:grid;grid-template-columns:1.4fr 1fr;gap:56px;align-items:start}
.three{display:grid;grid-template-columns:repeat(3,1fr);gap:32px}
.venues{list-style:none}.venues li{padding:10px 0;border-bottom:1px solid var(--line2);display:flex;justify-content:space-between;gap:12px;align-items:baseline}
.venues li .k{color:var(--accent);white-space:nowrap}
.venues h4{color:var(--soft);margin-bottom:8px}
table.rank{width:100%;border-collapse:collapse}table.rank th{text-align:left;padding:8px 0;border-bottom:1px solid var(--line);color:var(--mute);font-weight:normal}
table.rank td{padding:12px 0;border-bottom:1px solid var(--line2);vertical-align:baseline}table.rank td.n{font-variation-settings:"opsz" 40,"wght" 460;font-size:20px}table.rank td.num{font-family:"Space Mono",monospace;font-size:13px}
.year{display:grid;grid-template-columns:repeat(12,1fr);gap:6px;align-items:end;height:90px;border-bottom:1px solid var(--line)}.year i{display:block;background:var(--accent);opacity:.85}.year i.now{background:var(--ink)}
.year-l{display:grid;grid-template-columns:repeat(12,1fr);gap:6px;margin-top:6px;color:var(--mute)}
.crumb{color:var(--mute);padding:0 0 18px}
.prose{max-width:66ch;font-size:19px;line-height:1.6}.prose p{margin:0 0 20px}
.dir{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.doorblk{background:var(--green);color:var(--ink);padding:clamp(5rem,12vh,9rem) var(--pad);text-align:center;position:relative;overflow:hidden;border-top:0}
.doorblk .ghost{position:absolute;pointer-events:none;background:center/contain no-repeat url(/assets/mark-cream.webp);width:min(620px,78vw);aspect-ratio:498/560;right:-16%;top:50%;transform:translateY(-50%) rotate(-7deg);opacity:.07}
.doorblk h3{font-family:"Fraunces",serif;font-variation-settings:"opsz" 90,"wght" 440;font-size:clamp(2.2rem,6.5vw,4.4rem);line-height:1.02;letter-spacing:-.02em;position:relative}
.doorblk p{margin:1.6rem auto 0;font-style:italic;font-variation-settings:"opsz" 30,"wght" 400;color:rgba(247,243,233,.82);max-width:38ch;position:relative}
.doorblk form{margin:3rem auto 0;max-width:30rem;display:flex;border-bottom:1px solid rgba(247,243,233,.4);position:relative}.doorblk input{flex:1;background:transparent;border:0;padding:.7rem 0;color:var(--ink);font-family:"Space Mono",monospace;font-size:.85rem;letter-spacing:.08em}.doorblk input::placeholder{color:rgba(247,243,233,.4)}
.doorblk button{background:transparent;border:0;color:var(--ink);font-family:"Space Mono",monospace;font-size:.66rem;letter-spacing:.24em;text-transform:uppercase;cursor:pointer;padding:.7rem 0 .7rem 1rem}
footer{padding:36px 0 44px;border-top:1px solid var(--line2)}.foot{display:grid;grid-template-columns:repeat(4,1fr);gap:28px;padding-bottom:36px;border-bottom:1px solid var(--line2)}.foot h5{margin-bottom:12px;color:var(--soft)}.foot ul{list-style:none}.foot li{padding:3px 0}
.sign{display:flex;justify-content:space-between;align-items:center;padding-top:26px;gap:12px;flex-wrap:wrap}.sign .line{font-variation-settings:"opsz" 40,"wght" 460;font-size:20px}.sign .mono{color:var(--mute)}
/* map */
#lmap{height:min(78vh,760px);min-height:460px;width:100%;background:#0a1610;border-radius:4px;overflow:hidden;border:1px solid var(--line2)}
.leaflet-container{background:#0a1610;font-family:"Space Mono",monospace}.leaflet-control-attribution{background:rgba(11,23,16,.7)!important;color:var(--mute)!important;font-size:9px!important}.leaflet-control-attribution a{color:var(--soft)!important}
.leaflet-control-zoom a{background:rgba(11,23,16,.85)!important;color:var(--ink)!important;border-color:var(--line)!important}
.cm{position:relative;width:100%;height:100%}.cm img{width:100%;height:100%;object-fit:contain;filter:drop-shadow(0 0 6px rgba(127,191,152,.6))}
.cm.live::before{content:"";position:absolute;inset:-30%;border-radius:50%;border:1px solid var(--accent);animation:halo 2.8s ease-out infinite;opacity:0}
@keyframes halo{0%{transform:scale(.4);opacity:.7}100%{transform:scale(1.6);opacity:0}}
.cm .lbl{position:absolute;left:110%;top:50%;transform:translateY(-50%);white-space:nowrap;color:var(--ink);font-size:10px;letter-spacing:.1em;text-transform:uppercase;text-shadow:0 1px 6px #0a1610}
.leaflet-popup-content-wrapper{background:rgba(11,23,16,.94);color:var(--ink);border-radius:4px;border:1px solid var(--line);box-shadow:0 20px 50px rgba(0,0,0,.5)}.leaflet-popup-tip{background:rgba(11,23,16,.94)}
.leaflet-popup-content{margin:0;width:260px!important}.pop .ph{aspect-ratio:16/10}.pop .cap h4{font-family:"Fraunces",serif;font-size:22px;font-variation-settings:"opsz" 72,"wght" 460;line-height:1.05}.pop .cap .mono{color:var(--accent);margin-bottom:.35rem}
.pop .go{display:block;padding:.7rem 1rem;color:var(--ink);border-top:1px solid var(--line2)}
#mfilter{display:flex;gap:16px;flex-wrap:wrap;margin:0 0 14px}#mfilter button{border:0;background:transparent;color:var(--mute);font:inherit;cursor:pointer;padding:0;border-bottom:1px solid transparent}#mfilter button.on{color:var(--ink);border-bottom-color:var(--accent)}
#panel{display:none;margin-top:18px;border-top:1px solid var(--line);padding-top:22px}
#panel .pgrid{display:grid;grid-template-columns:1.2fr 1fr;gap:28px;align-items:start}
#panel .ph.main{aspect-ratio:16/10;border-radius:3px}#panel .strip{display:flex;gap:8px;margin-top:8px;overflow-x:auto}#panel .strip .ph{flex:0 0 140px;aspect-ratio:4/3;border-radius:2px;cursor:pointer}#panel .strip .ph::after{opacity:.5}
#panel h3{font-variation-settings:"opsz" 72,"wght" 460;font-size:clamp(1.8rem,3.4vw,2.6rem);line-height:1.05;margin:.4rem 0 .6rem}#panel .pnote{font-size:18px;color:var(--soft);max-width:48ch}
#panel .rooms{display:grid;grid-template-columns:repeat(3,1fr);gap:22px;margin-top:22px}#panel .rooms ul{list-style:none}#panel .rooms li{padding:7px 0;border-bottom:1px solid var(--line2);display:flex;justify-content:space-between;gap:8px;align-items:baseline}#panel .rooms h4{color:var(--soft);margin-bottom:6px}#panel .rooms .ap{color:var(--accent);white-space:nowrap}
@media (max-width:900px){
 .hnav .links{display:none}.hnav .menu{display:block}.two,#panel .pgrid{grid-template-columns:1fr}.three,.dir,.foot,#panel .rooms{grid-template-columns:1fr}
 .gallery{grid-template-columns:1fr 1fr;grid-auto-rows:150px}.gallery .ph:first-child{grid-column:span 2}
 .facts div:nth-child(odd){border-right:0;padding-right:0}.facts div:nth-child(even){padding-left:0}
 #lmap{height:70vh;min-height:420px}.rail>*{flex:0 0 82vw}
}
@media (prefers-reduced-motion:reduce){.ticker-track,.hero .bg img,.cm.live::before{animation:none}[data-reveal]{opacity:1;transform:none;transition:none}}
"""

SB_JS = f"""<script>
const SB="{SB_URL}",SK="{SB_KEY}";
async function sb(q){{try{{const r=await fetch(SB+"/rest/v1/"+q,{{headers:{{apikey:SK,Authorization:"Bearer "+SK}}}});return r.ok?await r.json():[]}}catch(e){{return[]}}}}
function fmtDate(s){{if(!s)return"";const d=new Date(s);return d.toLocaleDateString("en-GB",{{day:"numeric",month:"long",year:"numeric"}})}}
const strip=b=>(b||"").replace(/<[^>]+>/g," ").replace(/\\s+/g," ").trim();
const io=new IntersectionObserver(es=>es.forEach(en=>{{if(en.isIntersecting){{en.target.classList.add("in");io.unobserve(en.target)}}}}),{{threshold:.1}});
function reveal(){{document.querySelectorAll("[data-reveal]:not(.in)").forEach(el=>io.observe(el))}}
document.addEventListener("DOMContentLoaded",reveal);
</script>"""

NAVL = [("Circuit", "/circuit/"), ("Places", "/places/"), ("The Games", "/the-games/"), ("Index", "/index/"), ("Map", "/map/"), ("Dispatches", "/latest/")]
def ticker():
    lines = [w["note"] for w in wire[:6]] or [r["note"] for r in reads[:6]]
    return '<div class="ticker" aria-hidden="true"><div class="ticker-track">' + "".join(f"<span>{esc(t)}</span>" for t in lines * 2) + "</div></div>"
def nav(current=None):
    links = "".join(f'<a href="{h}"{" style=color:var(--ink)" if h == current else ""}>{n}</a>' for n, h in NAVL)
    return f'<nav class="hnav"><a class="brand" href="/"><img src="/assets/mark-cream.webp" alt=""><span class="wordmark">The Coriumist</span></a><div class="links">{links}<a class="door" href="/#door">The Door</a></div><button class="menu mono" aria-label="Menu" aria-expanded="false" onclick="document.body.classList.toggle(\'menu-open\');this.setAttribute(\'aria-expanded\',document.body.classList.contains(\'menu-open\'))">Menu</button></nav><div class="sheet"><div class="mono" style="color:var(--mute);margin-bottom:1.2rem">The Coriumist</div>{links}<a href="/#door">The Door</a></div>' + ticker()
def figure(p, cap="", cls="ph", lazy=True):
    if not p: return f'<div class="{cls}"><div class="cap">{cap}</div></div>'
    cr = esc(p.get("credit", "")) + (f'. {esc(p.get("license",""))}' if p.get("license") else "")
    return f'<figure class="{cls}"><img src="{esc(p["url"])}" alt="" {"loading=lazy" if lazy else "fetchpriority=high"}><div class="cap">{cap}</div><figcaption class="credit mono">{cr}</figcaption></figure>'
def foot():
    return f"""<footer><div class="wrap"><div class="foot mono">
<div><h5>The circuit</h5><ul><li><a href="/circuit/">Cities</a></li><li><a href="/map/">Map</a></li><li><a href="/index/">The Index</a></li><li><a href="/places/">Places</a></li></ul></div>
<div><h5>The desk</h5><ul><li><a href="/latest/">Dispatches</a></li><li><a href="/the-games/">The Games</a></li></ul></div>
<div><h5>The data</h5><ul><li><a href="/methodology/">Methodology</a></li><li><a href="/data/read.json">Today's read (JSON)</a></li></ul></div>
<div><h5>The Coriumist</h5><ul><li><a href="mailto:coriumist.ops@gmail.com">Contact</a></li><li><a href="https://www.instagram.com/coriumist">Instagram</a></li></ul></div></div>
<div class="sign"><span class="line">Money moves. We map it.</span><span class="mono">Public sources. City level. Never an address. The Coriumist, {TODAY.year}.</span></div></div></footer>"""
def shell(title, body, current=None, desc="Where capital congregates, by season and coordinate. Public record only.", head="", og=None):
    ogt = f'<meta property="og:image" content="{esc(og)}">' if og else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(title)}</title><meta name="description" content="{esc(desc)}">{ogt}{FONTS}<style>{CSS}</style>{SB_JS}{head}</head>
<body><div class="grain" aria-hidden="true"></div>{nav(current)}<main>{body}</main>{foot()}</body></html>"""
def write(path, content):
    full = os.path.join(SITE, path); os.makedirs(os.path.dirname(full), exist_ok=True); open(full, "w").write(content)

# ----------------------------------------------------------------- map component (Leaflet)
MAP_HTML = f"""
<div class="mono" id="mfilter"><button data-f="all" class="on">All forty</button><button data-f="active">Open and opening</button><button data-f="1">Permanent capitals</button><button data-f="2">Seasonal</button></div>
<div id="lmap" role="application" aria-label="The circuit map"></div>
<div id="panel"></div>
<p class="disc mono">{DISCLAIMER}. Map tiles © OpenStreetMap contributors, © CARTO.</p>
<script>
(async()=>{{
const read=await (await fetch("/data/read.json?d={TODAY.isoformat()}")).json();
const ST={{opening:"Opening",open:"Open",closing:"Closing",dispersing:"Dispersing",flat:"Flat",quiet:"Quiet"}};
const mobile=matchMedia("(max-width:900px)").matches;
const map=L.map("lmap",{{worldCopyJump:true,minZoom:1,maxZoom:15,zoomControl:!mobile,attributionControl:true,scrollWheelZoom:false}});
L.tileLayer("https://{{s}}.basemaps.cartocdn.com/dark_nolabels/{{z}}/{{x}}/{{y}}{{r}}.png",{{attribution:"&copy; OpenStreetMap &copy; CARTO",subdomains:"abcd",maxZoom:19}}).addTo(map);
L.tileLayer("https://{{s}}.basemaps.cartocdn.com/dark_only_labels/{{z}}/{{x}}/{{y}}{{r}}.png",{{subdomains:"abcd",maxZoom:19,opacity:.55,pane:"shadowPane"}}).addTo(map);
map.fitBounds([[-40,-125],[62,150]],{{padding:[10,10]}});
let approved=new Set();
try{{const a=await (await fetch("{SB_URL}/rest/v1/venues?approved=eq.true&select=city_slug,slug",{{headers:{{apikey:"{SB_KEY}",Authorization:"Bearer {SB_KEY}"}}}})).json();approved=new Set(a.map(x=>x.city_slug+"/"+x.slug))}}catch(e){{}}
const panel=document.getElementById("panel");
const fig=(p,cls)=>p?`<figure class="ph ${{cls||""}}"><img src="${{p.url}}" alt="" loading="lazy"><figcaption class="credit mono">${{p.credit||""}}${{p.license?". "+p.license:""}}</figcaption></figure>`:`<div class="ph ${{cls||""}}"></div>`;
function col(d,kind,label){{const rs=(read.rooms[d.slug]||[]).filter(r=>r.k===kind).slice(0,5);return `<div><h4 class="mono">${{label}}</h4><ul>${{rs.map(r=>`<li><a href="/places/${{d.slug}}/${{r.s}}/">${{r.n}}</a>${{approved.has(d.slug+"/"+r.s)?'<span class="ap mono">Approved</span>':''}}</li>`).join("")}}</ul></div>`}}
function show(d,noscroll){{panel.style.display="block";const ps=d.photos||[];
 panel.innerHTML=`<div class="pgrid"><div>${{fig(ps[0],"main")}}<div class="strip">${{ps.slice(1,6).map((p,i)=>`<div class="ph" data-i="${{i+1}}"><img src="${{p.url}}" alt="" loading="lazy"></div>`).join("")}}</div></div>
 <div><div class="mono" style="color:var(--accent)">${{ST[d.state]}} · Score ${{d.score}} · ${{"●".repeat(d.rings)}}</div><h3><a href="/circuit/${{d.slug}}/">${{d.name}}</a></h3><p class="pnote">${{d.note}}</p><p style="margin-top:14px"><a class="btn" href="/circuit/${{d.slug}}/">The destination</a></p></div></div>
 <div class="rooms">${{col(d,"hotel","Hotels")}}${{col(d,"restaurant","Restaurants")}}${{col(d,"attraction","Attractions and nightlife")}}</div>`;
 panel.querySelectorAll(".strip .ph").forEach(el=>el.onclick=()=>{{const p=ps[+el.dataset.i];panel.querySelector(".ph.main img").src=p.url;panel.querySelector(".ph.main .credit").textContent=(p.credit||"")+(p.license?". "+p.license:"")}});
 if(!noscroll)panel.scrollIntoView({{behavior:"smooth",block:"start"}})}}
const markers=[];
read.cities.forEach(d=>{{const size=16+d.rings*4;const live=d.state==="open"||d.state==="opening";
 const icon=L.divIcon({{className:"",html:`<div class="cm ${{live?"live":""}}"><img src="/assets/mark-cream.webp" alt="">${{d.rings>=4?`<span class="lbl">${{d.name}}</span>`:""}}</div>`,iconSize:[size,size*1.12],iconAnchor:[size/2,size*.56]}});
 const m=L.marker([d.lat,d.lon],{{icon,riseOnHover:true}}).addTo(map);
 const p0=(d.photos||[])[0];
 m.bindPopup(`<div class="pop">${{fig(p0)}}<div class="cap"><div class="mono">${{ST[d.state]}} · ${{d.score}}</div><h4>${{d.name}}</h4></div><a class="go mono" href="#panel" data-slug="${{d.slug}}">Hotels, restaurants, the rooms →</a></div>`,{{closeButton:false,maxWidth:280}});
 m.on("click",()=>{{show(d)}});m.on("popupopen",e=>{{const a=e.popup.getElement().querySelector(".go");if(a)a.onclick=ev=>{{ev.preventDefault();show(d)}}}});
 markers.push({{m,d}})}});
document.querySelectorAll("#mfilter button").forEach(b=>b.onclick=()=>{{document.querySelectorAll("#mfilter button").forEach(x=>x.classList.remove("on"));b.classList.add("on");const f=b.dataset.f;
 markers.forEach(({{m,d}})=>{{const on=f==="all"||(f==="active"?(d.state==="open"||d.state==="opening"):d.tier===+f);m.getElement().style.opacity=on?"1":".18"}})}});
show(read.cities[0],true);
}})();
</script>"""

# ----------------------------------------------------------------- pages
DOOR = """<section class="doorblk" id="door"><div class="ghost" aria-hidden="true"></div><h3>The door is currently closed.</h3><p>Leave an address. When the door opens, it opens in order of arrival.</p>
<form name="door" method="POST" action="/door/" data-netlify="true" netlify-honeypot="field"><input type="hidden" name="form-name" value="door"><input type="text" name="field" style="display:none" tabindex="-1" autocomplete="off"><input type="email" name="email" placeholder="Email" required aria-label="Email"><button type="submit">Enter</button></form></section>"""
MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

def city_card(r, wide=False):
    c = cities_by_slug[r["slug"]]; p = hero(r["slug"])
    cap = f'<div class="k mono"><span>{TIER_WORD[c["tier"]]}</span><span>{STATE_WORD[r["state"]]} · {r["score"]}</span></div><h3>{esc(c["name"])}</h3><p>{esc(r["note"])}</p><div class="st mono">Five hotels · five tables · five rooms →</div>'
    return f'<a class="card{" wide" if wide else ""}" href="/circuit/{r["slug"]}/">{figure(p, cap)}</a>'

# ---- home
hero_p = hero(reads[0]["slug"]) or next((hero(r["slug"]) for r in reads if hero(r["slug"])), None)
fallback_photos = [hero(r["slug"])["url"] for r in reads if hero(r["slug"])][:12]
home = f"""
<header class="hero" id="top"><div class="bg">{f'<img src="{esc(hero_p["url"])}" alt="" fetchpriority="high">' if hero_p else ""}</div>
 <div class="hero-stage"><p class="hero-eyebrow mono">A private intelligence publication</p><div class="mark-hero" role="img" aria-label="The Coriumist"></div><p class="hero-the">The</p><h1 class="hero-title">Coriumist</h1><p class="hero-deck">Where capital congregates.</p><p class="hero-sub mono">Public record, read closely &nbsp;·&nbsp; est. MMXXVI</p></div>
 <p class="where mono">{esc(reads[0]["name"])} is open. {esc(date_long(TODAY))}.</p><p class="hero-cue mono">Scroll</p></header>

<section id="circuit"><div class="wrap"><div class="railhead"><div><p class="eyebrow mono" style="margin-bottom:.6rem">01 · The circuit this week</p><h2 class="big" style="font-size:clamp(1.8rem,4vw,3rem)">Six places carrying the weight.</h2></div><div class="nav"><button aria-label="Back" data-rail="crail" data-dir="-1">←</button><button aria-label="Forward" data-rail="crail" data-dir="1">→</button></div></div>
 <div class="rail" id="crail" data-reveal>{"".join(city_card(r) for r in reads[:8])}</div>
 <p class="mono" style="margin-top:.6rem;color:var(--mute)"><a href="/index/">All forty, ranked</a></p></div></section>

<section id="dispatches"><div class="wrap"><div class="railhead"><div><p class="eyebrow mono" style="margin-bottom:.6rem">02 · Dispatches</p><h2 class="big" style="font-size:clamp(1.8rem,4vw,3rem)">Filed from the circuit.</h2></div><div class="nav"><button aria-label="Back" data-rail="drail" data-dir="-1">←</button><button aria-label="Forward" data-rail="drail" data-dir="1">→</button></div></div>
 <div class="rail wide" id="drail" data-reveal></div>
 <p style="margin-top:1rem"><a class="btn" href="/latest/">View all dispatches</a></p></div></section>

<section id="map"><div class="wrap"><p class="eyebrow mono">03 · The map</p><h2 class="big" style="font-size:clamp(1.8rem,4vw,3rem);margin-bottom:1.4rem">Forty cities. Tap one.</h2>{MAP_HTML}</div></section>
{DOOR}
<script>
window.FALLBACK={json.dumps(fallback_photos)};
(async()=>{{
 const rows=await sb("content?status=eq.published&select=id,format,title,body,publish_at,media_urls&order=publish_at.desc&limit=5");
 const grid=document.getElementById("drail");
 const card=(r,i)=>{{const img=(r.media_urls&&r.media_urls[0])||FALLBACK[i%FALLBACK.length]||"";return `<a class="card wide" href="/read/?id=${{r.id}}"><figure class="ph">${{img?`<img src="${{img}}" alt="" loading="lazy">`:""}}<div class="cap"><div class="k mono"><span>${{r.format||"Dispatch"}}</span><span>${{fmtDate(r.publish_at)}}</span></div><h3>${{r.title}}</h3><p>${{strip(r.body).slice(0,150)}}</p></div></figure></a>`}};
 grid.innerHTML=rows.length?rows.map(card).join(""):`<a class="card wide" href="/latest/"><figure class="ph"><img src="${{FALLBACK[0]||""}}" alt=""><div class="cap"><div class="k mono"><span>Dispatch</span></div><h3>Filed when it is filed.</h3><p>The first pieces publish through the article pipeline and appear here.</p></div></figure></a>`;
 document.querySelectorAll("[data-rail]").forEach(b=>b.onclick=()=>{{const r=document.getElementById(b.dataset.rail);r.scrollBy({{left:+b.dataset.dir*(r.firstElementChild?.offsetWidth+18||400),behavior:"smooth"}})}});
}})();
</script>"""
write("index.html", shell("The Coriumist", home, "/", head=LEAFLET, og=hero_p["url"] if hero_p else None))

# ---- map page
write("map/index.html", shell("The Map. The Coriumist", f'<section style="border:0;padding-top:1rem"><div class="wrap"><p class="eyebrow mono">The map</p><h1 class="big">Forty cities at today\'s weight.</h1><p class="dek">Tap a mark for the read, the photographs and the rooms: five hotels, five restaurants, five places to be after dark.</p></div></section><section style="padding-top:0;border:0"><div class="wrap">{MAP_HTML}</div></section>', "/map/", head=LEAFLET))

# ---- index
rows = "".join(f'<tr><td class="num">{i+1:02d}</td><td class="n"><a href="/circuit/{r["slug"]}/">{esc(r["name"])}</a></td><td class="mono">{TIER_WORD[r["tier"]]}</td><td class="mono">{STATE_WORD[r["state"]]}</td><td class="num">{r["score"]}</td><td class="num">{"●"*r["rings"]}</td><td class="num">{"+" if r["slope"]>0 else ""}{r["slope"]:.2f}</td></tr>' for i, r in enumerate(reads))
write("index/index.html", shell("The Coriumist Index", f"""<section style="border:0;padding-top:1rem"><div class="wrap"><p class="eyebrow mono">The Index</p><h1 class="big">Forty cities, one number each.</h1><p class="dek">Concentration of the circuit as of {esc(date_long(TODAY))}, on a calendar-weighted read. Rings are the number the mark carries. <a href="/methodology/">How the number is made.</a></p></div></section>
<section><div class="wrap"><table class="rank"><thead><tr class="mono"><th></th><th>City</th><th>Tier</th><th>State</th><th>Score</th><th>Rings</th><th>Trend</th></tr></thead><tbody>{rows}</tbody></table><p class="disc mono">{DISCLAIMER}</p></div></section>""", "/index/"))

# ---- circuit directory
dir_html = "".join(city_card(reads_by_slug[c["slug"]]) for c in sorted(DATA["cities"], key=lambda c: (c["tier"], -reads_by_slug[c["slug"]]["score"])))
write("circuit/index.html", shell("The Circuit. Forty cities", f'<section style="border:0;padding-top:1rem"><div class="wrap"><p class="eyebrow mono">The circuit</p><h1 class="big">Forty cities.</h1><p class="dek">Ten permanent capitals that never disappear. Thirty seasonal capitals that become the centre of gravity and then stop.</p></div></section><section><div class="wrap"><div class="dir">{dir_html}</div></div></section>', "/circuit/"))

# ---- city pages
for r in reads:
    c = cities_by_slug[r["slug"]]; ps = photos(c["slug"])
    active = sorted(((int(k), v) for k, v in c["months"].items()), key=lambda x: x[0]); peak = max(active, key=lambda x: x[1]["w"]) if active else None
    bars = "".join(f'<i class="{"now" if k+1==TODAY.month else ""}" style="height:{max(4, v)}%" title="{MON[k]} {v}"></i>' for k, v in enumerate(r["year"]))
    gal = f'<div class="gallery">{"".join(figure(p) for p in ps[:5])}</div>' if len(ps) > 1 else ""
    rooms = "".join(f'<div><h4 class="mono">{lbl}</h4><ul class="venues">' + "".join(f'<li><a href="/places/{c["slug"]}/{v["slug"]}/">{esc(v["name"])}</a><span class="k mono" data-v="{v["slug"]}"></span></li>' for v in c["venues"] if v["kind"] == k) + "</ul></div>" for k, lbl in KIND_WORD.items())
    windows = "".join(f'<div><dt class="mono">{calendar.month_name[k]}</dt><dd>{esc(v["note"])}</dd></div>' for k, v in active)
    body = f"""
<header class="hero" style="height:76svh;min-height:520px"><div class="bg">{f'<img src="{esc(ps[0]["url"])}" alt="" fetchpriority="high">' if ps else ""}</div>
 <div class="hero-stage" style="justify-content:flex-end;align-items:flex-start;text-align:left;padding-bottom:3rem"><div class="wrap" style="width:100%"><p class="crumb mono"><a href="/circuit/">The circuit</a> / {TIER_WORD[c["tier"]]}</p><h1 class="big" style="font-size:clamp(3rem,9vw,7rem)">{esc(c["name"])}</h1><p class="dek" style="color:var(--ink)">{esc(c["why"])}</p><p class="mono" style="margin-top:1rem;color:var(--accent)">{STATE_WORD[r["state"]]} · Score {r["score"]} · {"●"*r["rings"]}</p></div></div>
 {f'<p class="where mono">{esc(ps[0].get("credit",""))}. {esc(ps[0].get("license",""))}</p>' if ps else ""}</header>
<section style="border:0"><div class="wrap two"><div><p class="eyebrow mono">The read, {esc(calendar.month_name[TODAY.month])}</p><p class="prose">{esc(r["note"])}</p>{gal}</div>
<aside><div class="facts"><dl><div><dt class="mono">State today</dt><dd>{STATE_WORD[r["state"]]}</dd></div><div><dt class="mono">Score</dt><dd>{r["score"]}</dd></div><div><dt class="mono">Rings</dt><dd>{"●"*r["rings"]}</dd></div><div><dt class="mono">Trend</dt><dd>{"Rising" if r["slope"]>0.05 else "Falling" if r["slope"]<-0.05 else "Holding"}</dd></div><div><dt class="mono">Peak</dt><dd>{calendar.month_name[peak[0]] if peak else "Year round"}</dd></div><div><dt class="mono">Rooms</dt><dd>{len(c["venues"])}</dd></div></dl></div>
<div style="margin-top:28px"><p class="eyebrow mono">The year</p><div class="year">{bars}</div><div class="year-l mono">{"".join(f"<span>{m}</span>" for m in MON)}</div></div></aside></div></section>
<section><div class="wrap"><p class="eyebrow mono">The rooms · Coriumist Approved where designated</p><div class="three">{rooms}</div></div></section>
<section><div class="wrap"><p class="eyebrow mono">The windows</p><div class="facts"><dl>{windows}</dl></div><p class="disc mono">{DISCLAIMER}</p></div></section>
<script>(async()=>{{const v=await sb("venues?city_slug=eq.{c["slug"]}&approved=eq.true&select=slug");const s=new Set(v.map(x=>x.slug));document.querySelectorAll("[data-v]").forEach(e=>{{if(s.has(e.dataset.v))e.textContent="Approved"}})}})();</script>"""
    write(f"circuit/{c['slug']}/index.html", shell(f"{c['name']}. The Coriumist Circuit", body, "/circuit/", desc=c["why"], og=ps[0]["url"] if ps else None))

# ---- places
pl = "".join(f'<section><div class="wrap"><div class="railhead"><h2 class="big" style="font-size:clamp(1.6rem,3vw,2.4rem)"><a href="/circuit/{c["slug"]}/">{esc(c["name"])}</a></h2><span class="mono" style="color:var(--mute)">{len(c["venues"])} rooms</span></div><div class="three">' + "".join(f'<div><h4 class="mono" style="color:var(--soft);margin-bottom:8px">{lbl}</h4><ul class="venues">' + "".join(f'<li><a href="/places/{c["slug"]}/{v["slug"]}/">{esc(v["name"])}</a></li>' for v in c["venues"] if v["kind"] == k) + "</ul></div>" for k, lbl in KIND_WORD.items()) + "</div></div></section>" for c in sorted(DATA["cities"], key=lambda c: (c["tier"], c["name"])))
write("places/index.html", shell("Places. The rooms on the circuit", f'<section style="border:0;padding-top:1rem"><div class="wrap"><p class="eyebrow mono">Places</p><h1 class="big">The rooms.</h1><p class="dek">Six hundred public venues where the circuit actually sits. Five hotels, five restaurants, five places after dark, in every city. The designation is ours.</p></div></section>{pl}', "/places/"))

for c in DATA["cities"]:
    ps = photos(c["slug"]); r = reads_by_slug[c["slug"]]
    for i, v in enumerate(c["venues"]):
        p = ps[i % len(ps)] if ps else None
        body = f"""
<header class="hero" style="height:60svh;min-height:440px"><div class="bg">{f'<img src="{esc(p["url"])}" alt="">' if p else ""}</div>
 <div class="hero-stage" style="justify-content:flex-end;align-items:flex-start;text-align:left;padding-bottom:3rem"><div class="wrap" style="width:100%"><p class="crumb mono"><a href="/places/">Places</a> / <a href="/circuit/{c["slug"]}/">{esc(c["name"])}</a> / {KIND_WORD[v["kind"]]}</p><h1 class="big" style="font-size:clamp(2.4rem,7vw,5.5rem)">{esc(v["name"])}</h1><p class="mono" id="v-status" style="margin-top:1rem;color:var(--accent)">On the map. Designation pending.</p></div></div>
 {f'<p class="where mono">{esc(c["name"])}. {esc(p.get("credit",""))}. {esc(p.get("license",""))}</p>' if p else ""}</header>
<section style="border:0"><div class="wrap two"><div><p class="eyebrow mono">Coriumist Approved</p><div class="prose"><p id="v-what" style="color:var(--mute)">The designation runs three sentences: what it is, who it attracts and why that matters, what to know before arriving. This room has not yet been designated.</p><p id="v-who"></p><p id="v-know"></p></div><p class="mono" id="v-date" style="color:var(--mute)"></p></div>
<aside><div class="facts"><dl><div><dt class="mono">City</dt><dd><a href="/circuit/{c["slug"]}/">{esc(c["name"])}</a></dd></div><div><dt class="mono">Kind</dt><dd>{KIND_WORD[v["kind"]].rstrip("s") if v["kind"]!="attraction" else "Attraction or nightlife"}</dd></div><div><dt class="mono">City state today</dt><dd>{STATE_WORD[r["state"]]}</dd></div><div><dt class="mono">City score</dt><dd>{r["score"]}</dd></div></dl></div><p style="margin-top:20px"><a class="btn" href="/circuit/{c["slug"]}/">The destination</a></p></aside></div></section>
<script>(async()=>{{const rr=await sb("venues?city_slug=eq.{c["slug"]}&slug=eq.{v["slug"]}&select=what,who,know,approved,updated_at");const d=rr[0];if(!d||!d.approved)return;document.getElementById("v-status").textContent="Coriumist Approved";const w=document.getElementById("v-what");w.style.color="";w.textContent=d.what||"";document.getElementById("v-who").textContent=d.who||"";document.getElementById("v-know").textContent=d.know||"";document.getElementById("v-date").textContent="Designated "+fmtDate(d.updated_at)}})();</script>"""
        write(f"places/{c['slug']}/{v['slug']}/index.html", shell(f"{v['name']}, {c['name']}. Coriumist Approved", body, "/places/", og=p["url"] if p else None))

# ---- dispatch archive (latest) and The Games: photo grid fed by Supabase
def feed_page(title, kicker, h1, dek, query, path, current):
    return shell(title, f"""<section style="border:0;padding-top:1rem"><div class="wrap"><p class="eyebrow mono">{kicker}</p><h1 class="big">{h1}</h1><p class="dek">{dek}</p></div></section>
<section><div class="wrap"><div class="dir" id="feed" data-reveal><p class="mono" style="color:var(--mute)">Loading.</p></div></div></section>
<script>window.FALLBACK={json.dumps(fallback_photos)};(async()=>{{const rows=await sb("{query}");const g=document.getElementById("feed");
g.innerHTML=rows.length?rows.map((r,i)=>{{const img=(r.media_urls&&r.media_urls[0])||FALLBACK[i%FALLBACK.length]||"";return `<a class="card wide" href="/read/?id=${{r.id}}"><figure class="ph">${{img?`<img src="${{img}}" alt="" loading="lazy">`:""}}<div class="cap"><div class="k mono"><span>${{r.format||"Dispatch"}}</span><span>${{fmtDate(r.publish_at)}}</span></div><h3>${{r.title}}</h3><p>${{strip(r.body).slice(0,150)}}</p></div></figure></a>`}}).join(""):'<p class="mono" style="color:var(--mute)">Nothing filed yet.</p>'}})();</script>""", current)
write("latest/index.html", feed_page("Dispatches. The Coriumist", "Dispatches", "Everything filed, in order.", "Four hundred words, no more. What moved, what it suggests, where to look next.", "content?status=eq.published&select=id,format,title,body,publish_at,media_urls&order=publish_at.desc&limit=200", "latest", "/latest/"))
write("the-games/index.html", feed_page("The Games. The Coriumist", "The Games", "Sport as a capital event.", "Racing, sailing, tennis, polo, the paddock. Who is in the box, what the box costs, and what the season is really for.", "content?status=eq.published&format=ilike.*game*&select=id,format,title,body,publish_at,media_urls&order=publish_at.desc&limit=60", "the-games", "/the-games/"))

# ---- article view
write("read/index.html", shell("The Coriumist", f"""
<header class="hero" id="a-hero" style="height:72svh;min-height:480px"><div class="bg"><img id="a-img" src="" alt="" style="display:none"></div>
 <div class="hero-stage" style="justify-content:flex-end;align-items:flex-start;text-align:left;padding-bottom:3rem"><div class="wrap" style="width:100%"><p class="crumb mono" id="a-kicker"><a href="/latest/">Dispatches</a></p><h1 class="big" id="a-title" style="font-size:clamp(2.2rem,6vw,4.8rem);max-width:22ch">Loading.</h1><p class="mono" id="a-date" style="margin-top:1rem;color:var(--accent)"></p></div></div></header>
<section style="border:0"><div class="wrap"><article class="prose" id="a-body"></article><p style="margin-top:2rem"><a class="btn" href="/latest/">All dispatches</a></p></div></section>
<script>window.FALLBACK={json.dumps(fallback_photos)};(async()=>{{const id=new URLSearchParams(location.search).get("id");if(!id){{location.replace("/latest/");return}}
const rows=await sb("content?id=eq."+encodeURIComponent(id)+"&status=eq.published&select=id,format,title,body,publish_at,media_urls&limit=1");const r=rows[0];
if(!r){{document.getElementById("a-title").textContent="Not filed, or not yet published.";return}}
document.title=r.title+". The Coriumist";document.getElementById("a-title").textContent=r.title;document.getElementById("a-kicker").innerHTML='<a href="/latest/">Dispatches</a> / '+(r.format||"Dispatch");document.getElementById("a-date").textContent=fmtDate(r.publish_at);
const img=(r.media_urls&&r.media_urls[0])||FALLBACK[Math.abs([...id].reduce((a,c)=>a+c.charCodeAt(0),0))%FALLBACK.length]||"";if(img){{const el=document.getElementById("a-img");el.src=img;el.style.display="block"}}
const b=r.body||"";document.getElementById("a-body").innerHTML=/<[a-z][\\s\\S]*>/i.test(b)?b:b.split(/\\n\\s*\\n/).map(p=>"<p>"+p.replace(/\\n/g,"<br>")+"</p>").join("");
}})();</script>""", "/latest/"))

# ---- door received
write("door/index.html", shell("Received. The Coriumist", """<section class="doorblk" style="min-height:70vh;display:flex;flex-direction:column;justify-content:center"><div class="ghost" aria-hidden="true"></div><h3>Received.</h3><p>When the door opens, it opens in order of arrival. You are in the order.</p><p style="margin-top:2rem"><a class="btn" href="/">Back to the circuit</a></p></section>"""))

# ---- methodology
write("methodology/index.html", shell("Methodology. The Coriumist", f"""<section style="border:0;padding-top:1rem"><div class="wrap"><p class="eyebrow mono">Methodology</p><h1 class="big">How the number is made.</h1></div></section>
<section><div class="wrap"><div class="prose">
<p>The circuit is forty cities. Ten are permanent capitals and carry a standing weight all year. Thirty are seasonal and carry a weight only in the months the calendar puts them in play. Those weights come from the published calendar of the circuit: the fairs, the regattas, the races, the sales, the summits, and the rooms that fill around them.</p>
<p>Each day the score blends this month's weight toward next month's by how far into the month we are. The result is a number from 0 to 100. The rings on the mark are that number in seven steps.</p>
<p>The state is read from the level and the slope. Opening when the weight is high and still rising early in the window. Open at full weight. Closing when the weight is high and the next month drops it. Dispersing in the month after a peak. Flat when a permanent capital sits below its usual line. Quiet otherwise.</p>
<p>The wire records state changes only. Nothing on the wire is a forecast.</p>
<p>The twelve dimensions of the Index are scored by the operator and layered onto the calendar read as they are entered. Where a dimension has not been scored, the calendar read stands alone.</p>
<p>Photography is licensed: operator photographs, Unsplash, or Wikimedia Commons under CC0, CC BY or CC BY-SA, credited on the image. Sources are public only. Outputs are city and venue level. Never an address, never an individual in real time.</p>
<p class="mono" style="color:var(--mute)">{DISCLAIMER}</p></div></div></section>"""))

# ---- sitemap, robots
urls = ["/", "/circuit/", "/places/", "/the-games/", "/index/", "/map/", "/methodology/", "/latest/"] + [f"/circuit/{c['slug']}/" for c in DATA["cities"]] + [f"/places/{c['slug']}/{v['slug']}/" for c in DATA["cities"] for v in c["venues"]]
write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>https://coriumist.com{u}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>" for u in urls) + "</urlset>")
write("robots.txt", "User-agent: *\nAllow: /\nSitemap: https://coriumist.com/sitemap.xml\n")
print(f"built {len(urls)} urls. photos for {sum(1 for c in DATA['cities'] if photos(c['slug']))} cities. top: " + ", ".join(f"{r['name']} {r['score']} {r['state']}" for r in reads[:6]))
