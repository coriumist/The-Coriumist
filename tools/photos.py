#!/usr/bin/env python3
"""
THE CORIUMIST . DESTINATION PHOTOGRAPHY

Fills data/photos.json with licensed photographs for every city on the circuit, several per city.
Sources, in order:
  1. data/photos-manual.json   operator-chosen images, always first
  2. Unsplash API              if UNSPLASH_ACCESS_KEY is set. Best quality. Hotlinks the Unsplash CDN as their terms require.
  3. Wikimedia Commons API     no key. CC0, CC BY, CC BY-SA, public domain only. Credit and licence kept for the caption.
Idempotent: a city with 4 or more photos is left alone unless --refresh is passed. Runs in GitHub Actions before build.py.
"""
import json, os, sys, time, urllib.parse, urllib.request, re, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CIRCUIT = json.load(open(os.path.join(ROOT, "data", "circuit.json")))
OUT = os.path.join(ROOT, "data", "photos.json"); MANUAL = os.path.join(ROOT, "data", "photos-manual.json")
REFRESH = "--refresh" in sys.argv; WANT = 6
UA = "TheCoriumist/1.0 (https://coriumist.com; coriumist.ops@gmail.com)"
QUERIES = {
 "london": ["Mayfair London", "London skyline Thames dusk"], "new-york": ["Manhattan skyline aerial", "Central Park aerial"],
 "miami": ["Miami Beach aerial", "Ocean Drive Miami Beach"], "monaco": ["Port Hercule Monaco", "Monte Carlo Casino"],
 "dubai": ["Dubai Marina skyline", "Burj Al Arab"], "singapore": ["Marina Bay Sands night", "Singapore skyline"],
 "hong-kong": ["Victoria Harbour Hong Kong", "Hong Kong skyline night"], "geneva": ["Jet d'Eau Geneva", "Lake Geneva"],
 "zurich": ["Zurich Limmat", "Lake Zurich"], "paris": ["Paris rooftops Eiffel Tower", "Place Vendôme"],
 "st-barths": ["Gustavia Saint Barthélemy", "Saint-Barthélemy beach"], "st-moritz": ["St. Moritz lake winter", "Badrutt's Palace"],
 "davos": ["Davos winter", "Schatzalp Davos"], "aspen": ["Aspen Colorado winter", "Aspen Mountain"],
 "palm-beach": ["Palm Beach Florida", "The Breakers Palm Beach"], "tokyo": ["Tokyo skyline", "Meguro River cherry blossom"],
 "los-angeles": ["Beverly Hills", "Los Angeles skyline sunset"], "cannes": ["Cannes Croisette", "Cannes Vieux Port"],
 "sun-valley": ["Sun Valley Idaho", "Bald Mountain Ketchum"], "porto-cervo": ["Porto Cervo marina", "Costa Smeralda"],
 "pebble-beach": ["Pebble Beach Golf Links", "17-Mile Drive"], "the-hamptons": ["Montauk Point Lighthouse", "East Hampton beach"],
 "mykonos": ["Mykonos windmills", "Little Venice Mykonos"], "ibiza": ["Es Vedrà", "Dalt Vila Ibiza"],
 "capri": ["Faraglioni Capri", "Marina Grande Capri"], "lake-como": ["Villa del Balbianello", "Bellagio Lake Como"],
 "gstaad": ["Gstaad village", "Gstaad winter"], "jackson-hole": ["Grand Teton", "Jackson Hole valley"],
 "nantucket": ["Nantucket harbor", "Brant Point Light"], "abu-dhabi": ["Yas Marina Circuit", "Sheikh Zayed Grand Mosque"],
 "venice": ["Venice Grand Canal", "Venice lagoon aerial"], "basel": ["Basel Rhine Mittlere Brücke", "Basel Münster"],
 "maastricht": ["Maastricht Vrijthof", "Maastricht Maas"], "milan": ["Milan Duomo", "Galleria Vittorio Emanuele II"],
 "courchevel": ["Courchevel ski", "Courchevel altiport"], "austin": ["Austin Texas skyline", "Circuit of the Americas"],
 "las-vegas": ["Las Vegas Strip night", "Bellagio fountains"], "monza": ["Autodromo Nazionale Monza", "Villa Reale di Monza"],
 "silverstone": ["Silverstone Circuit", "Stowe House"], "melbourne": ["Melbourne skyline Yarra", "Albert Park Melbourne"],
}
OK = ("cc0", "cc by", "cc-by", "public domain", "pd-", "no restrictions", "attribution")
def get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=40) as r: return json.loads(r.read().decode())
def strip(s): return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()
def commons(query, n):
    q = urllib.parse.quote(f"filetype:bitmap {query}")
    url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search"
           f"&gsrsearch={q}&gsrnamespace=6&gsrlimit=40&prop=imageinfo&iiprop=url|size|extmetadata&iiurlwidth=1800")
    try: data = get(url)
    except Exception as e: print("  commons error", e); return []
    out = []
    for p in sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0)):
        ii = (p.get("imageinfo") or [{}])[0]; w, h = ii.get("width", 0), ii.get("height", 0)
        if w < 1600 or h < 900 or w < h * 1.15 or not ii.get("url", "").lower().endswith((".jpg", ".jpeg")): continue
        md = ii.get("extmetadata", {}); lic = (md.get("LicenseShortName", {}).get("value") or "").lower()
        if not any(k in lic for k in OK) or "-nc" in lic or "-nd" in lic: continue
        out.append({"url": ii.get("thumburl") or ii["url"], "full": ii["url"], "w": w, "h": h, "credit": strip(md.get("Artist", {}).get("value"))[:80] or "Wikimedia Commons",
                    "license": md.get("LicenseShortName", {}).get("value", ""), "page": ii.get("descriptionurl", ""), "source": "commons", "q": query})
        if len(out) >= n: break
    return out
def unsplash(query, n, key):
    url = f"https://api.unsplash.com/search/photos?query={urllib.parse.quote(query)}&orientation=landscape&per_page={n}&content_filter=high"
    try: data = get(url, {"Authorization": f"Client-ID {key}", "Accept-Version": "v1"})
    except Exception as e: print("  unsplash error", e); return []
    return [{"url": r["urls"]["regular"], "full": r["urls"]["full"], "w": r["width"], "h": r["height"], "credit": r["user"]["name"],
             "credit_url": r["user"]["links"]["html"] + "?utm_source=the_coriumist&utm_medium=referral", "license": "Unsplash License",
             "page": r["links"]["html"] + "?utm_source=the_coriumist&utm_medium=referral", "download": r["links"]["download_location"], "source": "unsplash", "q": query}
            for r in data.get("results", [])]
photos = json.load(open(OUT)) if os.path.exists(OUT) else {}
manual = json.load(open(MANUAL)) if os.path.exists(MANUAL) else {}
key = os.environ.get("UNSPLASH_ACCESS_KEY")
for c in CIRCUIT["cities"]:
    s = c["slug"]; man = [dict(p, source="manual") for p in manual.get(s, [])]
    auto = [p for p in photos.get(s, []) if p.get("source") != "manual"]
    if len(man) + len(auto) >= 4 and not REFRESH: photos[s] = (man + auto)[:WANT]; continue
    got = []
    for q in QUERIES.get(s, [c["name"]]):
        got += unsplash(q, 3, key) if key else commons(q, 4); time.sleep(0.5)
    seen, dedup = set(), []
    for p in got:
        if p["url"] not in seen: seen.add(p["url"]); dedup.append(p)
    photos[s] = (man + dedup)[:WANT]; print(f"{c['name']}: {len(photos[s])}")
json.dump(photos, open(OUT, "w"), indent=1, ensure_ascii=False)
print("cities with photos:", sum(1 for c in CIRCUIT["cities"] if photos.get(c["slug"])), "of", len(CIRCUIT["cities"]))
