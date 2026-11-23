#!/usr/bin/env python3
"""Build portthings.com from the Port Things app's own catalog and guide packs.

    python3 tools/build_site.py            # rebuild Home, every guide page, covers, sitemap, robots
    python3 tools/build_site.py --check    # also print a per-guide summary

Reads (READ-ONLY) the hub app, ~/ThingsHub/ThingsHub:
    Catalog/catalog.json            which guides exist, status (live / building / hidden), shelves, region packs
    Packs/manifest.json             the counts the app's store sheet shows (places, ready-made days, piers)
    Packs/<id>.json                 languages, area names, piers + typical hours, day-plan titles (English)
    Covers.xcassets/cover-<id>...   Dan's cover art (his app icons), copied and only RESIZED for the web

Only guides with status "live" get a card and a page. Hidden guides (Mazatlan, Alaska) are left out
everywhere, including the region-pack lists. Guides flagged placeholderIcon get a plain name card,
exactly like Home in the app -- never generated art.

Writes (inside this repo only):
    index.html, guide/<id>/index.html, covers/<id>.png, sitemap.xml, robots.txt

App Store link: /app-store.json {"PortThings": ""}. Put the numeric App Store ID there when Apple
approves the app, re-run this script and push. The pages also read that file at load time, so the
"Coming soon to the App Store" badge turns into the App Store link even before a rebuild.
Prices are deliberately NOT on the site (they live in App Store Connect and may change).
"""
import html, json, os, shutil, subprocess, sys
from datetime import date

HOME = os.path.expanduser("~")
HUB = os.path.join(HOME, "ThingsHub", "ThingsHub")
SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://portthings.com"
APP_NAME = "Port Things"
WORD = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
INCLUDED = 5   # set from catalog.json includedGuides in build_model()
SUPPORT_EMAIL = "info@incmpltellc.com"
COVER_PX = 360          # 1024 source -> 360 (tiles are <= 180 CSS px wide at 2x)
E = html.escape

LANG = {"en": "English", "es": "Spanish", "fr": "French", "pt-BR": "Portuguese (Brazil)", "de": "German",
        "it": "Italian", "nl": "Dutch", "ru": "Russian", "pl": "Polish", "zh-Hans": "Chinese (Simplified)",
        "sv": "Swedish", "is": "Icelandic"}
SHELF = {
    "cruise": dict(title="Cruise ports",
                   sub="Port-day guides: walking minutes from the pier and plans that get you back before all-aboard."),
    "trips": dict(title="Trips",
                  sub="Fly-in and road-trip guides, each one on its own."),
}


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# Screenshot gallery on the home page (Dan 23 Nov 2026: "lots of screenshots, including directions").
# Sources = the app's UI-test captures in ~/Screenshots/ThingsHub (iPhone 17 Pro Max), read-only;
# copied to shots/ and resized. NO prices on the site, so the store sheet and planner shots stay out.
SHOT_SRC = os.path.join(HOME, "Screenshots", "ThingsHub")
SHOT_PX = 1100          # long edge; shown <= ~260 CSS px wide
SHOTS = [
    ("08-home-trips-shelf", "home", "Every port, grouped by region"),
    ("04-owned-guide-explore", "explore", "Traveler guides and ready-made port days"),
    ("10-day-plan", "day-plan", "Port days timed around all-aboard"),
    ("11-traveler-guide", "arrival", "Arrival day: your pier, taxis, money"),
    ("12-place", "place", "Walking minutes from your pier"),
    ("05-owned-guide-map", "map", "Every place on the map"),
    ("06b-apple-maps-howto", "directions", "Offline directions: save your port in Apple Maps"),
    ("real-phone/juneau-offline-no-internet", "offline-route", "No internet in Juneau: turn-by-turn from the pier still works"),
    ("real-phone/juneau-offline-walking", "offline-walking", "Walking directions from the pier, offline: 26 min to the whale-watch dock"),
    ("07-offline-apple-maps-buttons", "offline", "Offline packs for every part of the port"),
    ("06-owned-stthomas", "st-thomas", "One app, every port: St. Thomas"),
]


def shots():
    os.makedirs(os.path.join(SITE, "shots"), exist_ok=True)
    out = []
    for src, name, caption in SHOTS:
        f = os.path.join(SHOT_SRC, f"{src}-iPhone17ProMax.png")
        if not os.path.exists(f):                       # real-phone shots (Dan's iPhone, 23 Nov 2026)
            f = os.path.join(SHOT_SRC, f"{src}-iPhone.png")
        if not os.path.exists(f):
            continue
        dst = os.path.join(SITE, "shots", f"{name}.jpg")
        if not (os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(f)):
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "82", "-Z", str(SHOT_PX), f,
                            "--out", dst], check=True, capture_output=True)
        out.append((name, caption))
    return out


def wr(rel, s):
    p = os.path.join(SITE, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


def num(n):
    return f"{n:,}"


def store_id():
    try:
        return str(load(os.path.join(SITE, "app-store.json")).get("PortThings", "")).strip()
    except FileNotFoundError:
        return ""


def badge(sid):
    if sid:
        return f'<a class="store" href="https://apps.apple.com/app/id{E(sid)}">Get {APP_NAME} on the App Store</a>'
    return '<span class="badge" data-app="PortThings">Coming soon to the App Store</span>'


def avail_line():
    return "On the App Store now." if store_id() else "Coming soon to the App Store."


# Swaps the badge for the store link as soon as app-store.json carries an ID (same as tulumthings.com).
STORE_JS = """<script>
fetch('/app-store.json').then(function(r){return r.json()}).then(function(j){
  var id=(j.PortThings||'').trim(); if(!id) return;
  document.querySelectorAll('span.badge[data-app="PortThings"]').forEach(function(b){
    var a=document.createElement('a');a.className='store';a.href='https://apps.apple.com/app/id'+id;
    a.textContent='Get Port Things on the App Store';b.replaceWith(a);});
}).catch(function(){});
</script>"""


def head(title, desc, url, image=None, extra=""):
    og_img = f'\n<meta property="og:image" content="{E(image)}">' if image else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{E(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{APP_NAME}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{E(url)}">{og_img}
<meta name="color-scheme" content="light dark">
<link rel="stylesheet" href="/style.css">{extra}
</head>
<body>
<main>
"""


FOOT = f"""
  <footer>© {date.today().year} Incmplte L.L.C. · <a href="https://incmpltellc.com/">Privacy</a> ·
  <a href="/support/">Support</a>
  <p class="credits">Place data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> (ODbL)
  and © <a href="https://overturemaps.org/">Overture Maps Foundation</a> (CDLA Permissive 2.0).
  Photos courtesy of <a href="https://commons.wikimedia.org/">Wikimedia Commons</a> and
  <a href="https://www.mapillary.com/">Mapillary</a> contributors (CC BY-SA); each photo is credited with the photo in the app.
  Map © Apple. Port Things is an independent guide, not affiliated with any venue, tour operator or tourism board.</p></footer>
</main>
{STORE_JS}
</body>
</html>
"""


def art(g, cls="cover"):
    """Dan's cover, or the app's plain name card for placeholder icons."""
    if g["hasCover"]:
        return f'<span class="{cls}"><img src="/covers/{g["id"]}.png" alt="" loading="lazy" width="{COVER_PX}" height="{COVER_PX}"></span>'
    return f'<span class="namecard" aria-hidden="true">{E(g["name"])}</span>'


# ------------------------------------------------------------------------------------------ model
# Live in the app's catalog but not yet buyable on the App Store: no page, no card, until the
# version that sells it is approved. Alaska ships in Port Things 1.0.1 (submitted Nov 2026) -
# remove it from this set the day 1.0.1 is live, rerun, push.
ON_HOLD = set()
# Dan 23 Nov 2026: show it now as "Coming soon" (card label + note on its page) while the app version
# that sells it is in review. Empty this set the day 1.0.1 is live, rerun, push.
COMING_SOON = {"alaska"}


def build_model():
    global INCLUDED
    cat = load(os.path.join(HUB, "Catalog", "catalog.json"))
    INCLUDED = cat.get("includedGuides", 5)
    man = load(os.path.join(HUB, "Packs", "manifest.json"))
    guides = []
    for c in cat["guides"]:
        if c.get("status") != "live" or c["id"] in ON_HOLD:
            continue
        gid = c["id"]
        pack = load(os.path.join(HUB, "Packs", f"{gid}.json"))
        counts = man[gid]["counts"]
        s = pack["strings"]
        en = lambda k: (s.get(k) or {}).get("en")
        area = {a["key"]: a["label"] for a in pack["areas"]}
        # Piers: one per distinct pierName, in the app's pierChoices order when it has one.
        ports = pack.get("ports") or {}
        order = (pack.get("pierChoices") or []) + [k for k in ports if k not in (pack.get("pierChoices") or [])]
        piers, seen = [], set()
        for k in order:
            p = ports.get(k)
            if not p or p["pierName"] in seen:
                continue
            seen.add(p["pierName"])
            # With no pierChoices each port is its own place (Norway's 19): name the place too.
            label = None if pack.get("pierChoices") or len(ports) == 1 else area.get(k)
            piers.append(dict(name=p["pierName"], place=label, hours=p.get("typicalHours")))
        pier_count = counts.get("piers") if counts.get("piers") is not None else counts["ports"]
        if counts["ports"] > 0:
            assert len(piers) == pier_count, (gid, len(piers), pier_count)
        trips = [dict(title=en(f"trip.{t['id']}.title") or t["id"], sub=en(f"trip.{t['id']}.sub"))
                 for t in pack["dayTrips"]]
        assert len(trips) == counts["dayTrips"], gid
        cover_src = os.path.join(HUB, "Covers.xcassets", f"cover-{gid}.imageset", "cover.png")
        has_cover = not c.get("placeholderIcon") and os.path.exists(cover_src)
        guides.append(dict(
            id=gid, name=c["name"], country=c["country"], shelves=c["shelves"],
            places=counts["venues"], days=counts["dayTrips"], piers=pier_count if counts["ports"] > 0 else 0,
            languages=pack["languages"], areas=[a["label"] for a in pack["areas"]],
            categories=[x["label"] for x in pack["categories"]],
            pierList=piers, trips=trips, hasCover=has_cover, coverSrc=cover_src,
            source=man[gid]["source"]))
    by = {g["id"]: g for g in guides}
    regions = []
    for r in (cat["regions"] if cat.get("sellRegionPacks", True) else []):
        live = [by[i] for i in r["guides"] if i in by]
        if live:
            regions.append(dict(id=r["id"], name=r["name"], guides=live))
    for g in guides:
        g["regions"] = [r["name"] for r in regions if g in r["guides"]]
        # Home grouping (Dan 23 Nov 2026, same rule as the app): the first catalog region listing the
        # guide, whether or not packs are sold; a guide in no region is its own heading (Alaska).
        home = next((r for r in cat["regions"] if g["id"] in r["guides"]), None)
        g["area"] = home["name"] if home else g["name"]
    return guides, regions


def covers(guides):
    os.makedirs(os.path.join(SITE, "covers"), exist_ok=True)
    for g in guides:
        if not g["hasCover"]:
            continue
        out = os.path.join(SITE, "covers", f"{g['id']}.png")
        if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(g["coverSrc"]):
            continue
        shutil.copyfile(g["coverSrc"], out)          # byte-for-byte copy of Dan's art ...
        subprocess.run(["sips", "-Z", str(COVER_PX), out], check=True, capture_output=True)  # ... then resize only


# ------------------------------------------------------------------------------------------ pages
def azkey(t):
    """A-Z ignoring case and accents (Roatán sorts with the Rs), like the app."""
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFKD", t) if not unicodedata.combining(ch)).casefold()


def card(g):
    where = g["country"]
    soon = '<span class="soon">Coming soon</span>' if g["id"] in COMING_SOON else ""
    return (f'    <li><a href="/guide/{g["id"]}/">{soon}{art(g)}<h3>{E(g["name"])}</h3>'
            f'<span class="where">{E(where)}</span></a></li>')


def render_home(guides, regions, sid):
    n = len(guides)
    inc = WORD.get(INCLUDED, str(INCLUDED))
    pack_li = ("\n    <li>or a <b>cruise-region pack</b> that covers every port in that part of the world,</li>" if regions else "")
    shelves = []
    for sh in ("cruise", "trips"):
        # Same order as the app's Home: cruise ports by region A-Z, ports A-Z inside; Trips A-Z.
        gs = sorted((g for g in guides if sh in g["shelves"]), key=lambda g: azkey(g["name"]))
        if not gs:
            continue
        if sh == "cruise":
            areas = sorted({g["area"] for g in gs}, key=azkey)
            body = "".join(f"""
  <h3 class="area">{E(a)}</h3>
  <ul class="shelf">
{chr(10).join(card(g) for g in gs if g["area"] == a)}
  </ul>""" for a in areas)
        else:
            body = f"""
  <ul class="shelf">
{chr(10).join(card(g) for g in gs)}
  </ul>"""
        shelves.append(f"""
  <h2 id="{sh}">{SHELF[sh]['title']}</h2>
  <p class="small">{E(SHELF[sh]['sub'])}</p>{body}""")
    packs = "\n".join(
        f'    <li><b>{E(r["name"])}</b><br><span>{E(", ".join(g["name"] for g in r["guides"]))}</span></li>'
        for r in regions)
    planner = (f"""  <p>Tick the ports on your itinerary and the app works out the cheapest way to cover them: a region pack,
  single guides, your included guides, or a mix. It leaves out anything you already own and shows any extra
  ports a pack unlocks.</p>
  <p>The cruise-region packs:</p>
  <ul class="packs">
{packs}
  </ul>
  <p class="small">Trips guides aren't in the region packs. Get them on their own or with All guides.</p>""" if regions else
               """  <p>Tick the ports on your itinerary and the app shows the cheapest way to cover them: your included
  guides first, then single guides or All guides. It leaves out anything you already own.</p>""")
    desc = (f"Port Things is one iOS app that holds {n} deep, offline travel guides to cruise ports and "
            "trips. Pick the ports on your cruise. " + avail_line())
    return head(f"{APP_NAME}: offline cruise port and travel guides", desc, BASE + "/", extra="""
<script>
// The app's own links also use https://portthings.com/?guide=<id>; send browsers to that guide's page.
(function(){var m=location.search.match(/[?&]guide=([a-z]+)/);if(m)location.replace('/guide/'+m[1]+'/');})();
</script>""") + f"""  <p class="kicker">{APP_NAME}</p>
  <h1>Deep, offline guides to every port. Pick the ones on your cruise.</h1>
  <p class="tagline">One iOS app, {n} destinations. Real places, ready-made port days that get you back
  before all-aboard, and a guide that keeps working with no signal.</p>
  <p>{badge(store_id())}</p>

  <ul class="promise">
    <li><span class="big">No subscription. Ever.</span>Buy it once. Add a guide only if you want one.</li>
    <li><span class="big">Offline maps</span>Every place, day plan and walking time is on your phone. No signal needed.</li>
    <li><span class="big">Offline directions</span>Save your port in Apple Maps with one tap and directions work at sea, with no roaming.</li>
  </ul>

  <h2 id="screens">See it</h2>
  <div class="shots">
{chr(10).join(f'    <figure><img src="/shots/{n}.jpg" alt="{E(c)}" loading="lazy" width="250"><figcaption>{E(c)}</figcaption></figure>' for n, c in SHOTS_BUILT)}
  </div>

  <ul class="points">
    <li><b>Deep, not wide</b>Thousands of real places per destination, with opening hours, descriptions and the
    area each one is in. Hand-picked highlights on top.</li>
    <li><b>Built for the port day</b>Walking minutes from your pier, day plans timed around the ship and an
    all-aboard reminder.</li>
    <li><b>Works offline</b>Every place, description and day plan is on the phone. Save the port in Apple Maps
    once and the map and directions work with no signal too.</li>
    <li><b>One app, your ports</b>No subscription, no account, no ads, no tracking. Most guides in eleven
    languages.</li>
  </ul>

  <h2>How it works</h2>
  <ul class="buy">
    <li>The app comes with <b>{inc} guides included</b>: pick any {inc} destinations.</li>
    <li>Add other guides one at a time,</li>{pack_li}
    <li>or <b>All guides</b>, including every guide we add later.</li>
  </ul>
{''.join(shelves)}

  <h2 id="cruise-planner">Which cruise are you taking?</h2>
{planner}
{FOOT}"""


def render_guide(g, sid):
    url = f"{BASE}/guide/{g['id']}/"
    langs = [LANG.get(l, l) for l in g["languages"]]
    is_cruise = "cruise" in g["shelves"]
    facts = [f'<li><b>{num(g["places"])}</b>places</li>',
             f'<li><b>{g["days"]}</b>ready-made days</li>']
    if g["piers"]:
        facts.append(f'<li><b>{g["piers"]}</b>cruise pier{"s" if g["piers"] != 1 else ""}</li>')
    facts.append(f'<li><b>{len(langs)}</b>languages</li>')
    kind = "cruise port guide" if is_cruise else "travel guide"
    desc = (f"The {g['name']} {kind} in Port Things: {num(g['places'])} places, {g['days']} ready-made days"
            + (f", {g['piers']} cruise pier{'s' if g['piers'] != 1 else ''}" if g["piers"] else "")
            + f", {len(langs)} languages, works offline. " + avail_line())
    image = f"{BASE}/covers/{g['id']}.png" if g["hasCover"] else None

    piers = ""
    if g["pierList"]:
        rows = []
        for p in g["pierList"]:
            name = f'{E(p["place"])}: {E(p["name"])}' if p["place"] else E(p["name"])
            rows.append(f'    <li>{name}</li>')
        hours = g["pierList"][0]["hours"] if len({p["hours"] for p in g["pierList"]}) == 1 else None
        piers = (f'\n  <h2>Where the ships dock</h2>\n  <ul class="piers">\n' + "\n".join(rows) + "\n  </ul>"
                 + (f'\n  <p class="small">{E(hours)}</p>' if hours else ""))
    trips = "\n".join(
        f'    <li><h3>{E(t["title"])}</h3>' + (f'<p>{E(t["sub"])}</p>' if t["sub"] else "") + "</li>"
        for t in g["trips"])
    areas = "\n".join(f"    <li>{E(a)}</li>" for a in g["areas"])
    cats = "\n".join(f"    <li>{E(c)}</li>" for c in g["categories"])
    packs = (f'<p>Also in the <b>{E(" and ".join(g["regions"]))}</b> pack, and in All guides.</p>'
             if g["regions"] else "<p>Get it on its own, or with All guides.</p>")
    soon_note = ('  <p class="soonnote"><b>Coming soon.</b> The ' + E(g["name"]) + ' guide arrives in the next'
                 ' Port Things update, now with Apple for review.</p>\n' if g["id"] in COMING_SOON else "")
    port_line = (" Every place shows walking minutes from your pier, and the day plans are timed around"
                 " the all-aboard." if is_cruise and g["piers"] else "")
    return head(f"{g['name']} guide | {APP_NAME}", desc, url, image) + f"""  <p class="crumbs"><a href="/">← All {APP_NAME} guides</a></p>
  <div class="guidehead">
    {art(g)}
    <div>
      <p class="kicker">{SHELF['cruise' if is_cruise else 'trips']['title']}</p>
      <h1>{E(g['name'])}</h1>
      <p class="tagline">{E(g['country'])}</p>
    </div>
  </div>

{soon_note}  <p>A deep, offline guide to {E(g['name'])}, inside the {APP_NAME} app.{port_line}
  Every place, description and day plan is on the phone, so it works with no signal. Save the port in Apple
  Maps once and the map and directions work offline too.</p>

  <ul class="facts">
    {chr(10).join('    ' + f for f in facts).strip()}
  </ul>
{piers}

  <h2>Ready-made days</h2>
  <ul class="trips">
{trips}
  </ul>

  <h2>Areas covered</h2>
  <ul class="chips">
{areas}
  </ul>

  <h2>What's in the map</h2>
  <ul class="chips">
{cats}
  </ul>

  <h2>Languages</h2>
  <p>{E(", ".join(langs))}.</p>

  <div class="cta">
    <div>
      <h2>Get the {E(g['name'])} guide</h2>
      <p>{APP_NAME} comes with {WORD.get(INCLUDED, INCLUDED)} guides included, so this can be one of them.</p>
      {packs}
      <p>{badge(sid)}</p>
    </div>
  </div>
{FOOT}"""


def render_support():
    inc = WORD.get(INCLUDED, str(INCLUDED))
    mail = f'<a href="mailto:{SUPPORT_EMAIL}?subject=Port%20Things">{SUPPORT_EMAIL}</a>'
    qa = [
        ("How do I pick my included guides?",
         f"The app comes with {inc} guides of your choice. Tap any destination on Home, then "
         "<b>Make this one of my included guides</b>. The banner on Home counts how many picks you have left."),
        ("I got a new phone or reinstalled the app.",
         "Sign in with the same Apple ID. Your included picks come back from your own iCloud, and anything you bought "
         "comes back with <b>Settings &rarr; Restore Purchases</b> in the app."),
        ("Does it really work without a signal?",
         "Yes. Every place, description, opening time and day plan is stored on your phone, so a guide works at sea and "
         "at the pier with no Wi-Fi or roaming. Photos for a guide download the first time you open it on Wi-Fi, and the "
         "map background needs a connection."),
        ("What does it cost?",
         f"The app is a one-time purchase with {inc} guides included. After that you can add single guides, or get "
         "<b>All guides</b>, which also includes every destination we add later. No subscriptions, no ads, no account."),
        ("Does Family Sharing work?",
         "Yes. The app and its in-app purchases support Family Sharing."),
        ("I'd like a refund.",
         'Apple handles all payments and refunds. Go to <a href="https://reportaproblem.apple.com">reportaproblem.apple.com</a>, '
         "sign in, and choose the purchase."),
        ("A place has closed or something is wrong in a guide.",
         f"Please tell us: email {mail} with the guide and the place's name. We fix guides in app updates."),
    ]
    items = "\n".join(f"  <h3>{q}</h3>\n  <p>{a}</p>" for q, a in qa)
    return head(f"Support | {APP_NAME}", f"Help with {APP_NAME}: included guides, restoring purchases, offline use, refunds and contact.",
                BASE + "/support/") + f"""  <p class="kicker"><a href="/">{APP_NAME}</a></p>
  <h1>Support</h1>
  <p class="tagline">Questions, a problem, or a place we got wrong? Email {mail} and a real person will answer.</p>
{items}
  <p class="small"><a href="https://incmpltellc.com/portthings/privacy.html">Privacy policy</a>: {APP_NAME} collects no data.</p>
{FOOT}"""


def render_404():
    return head(f"Not found | {APP_NAME}", "This page isn't here.", BASE + "/") + f"""  <h1>That page isn't here.</h1>
  <p>It may be a guide that isn't out yet. <a href="/">See every {APP_NAME} guide</a>.</p>
{FOOT}"""


def main():
    check = "--check" in sys.argv
    sid = store_id()
    guides, regions = build_model()
    covers(guides)
    global SHOTS_BUILT
    SHOTS_BUILT = shots()
    wr("index.html", render_home(guides, regions, sid))
    for g in guides:
        wr(f"guide/{g['id']}/index.html", render_guide(g, sid))
    wr("404.html", render_404())
    wr("support/index.html", render_support())
    today = date.today().isoformat()
    urls = [BASE + "/", BASE + "/support/"] + [f"{BASE}/guide/{g['id']}/" for g in guides]
    wr("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
       '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
       + "".join(f"  <url><loc>{u}</loc><lastmod>{today}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    wr("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {BASE}/sitemap.xml\n")
    # Pages for guides that are no longer live must not linger.
    gdir = os.path.join(SITE, "guide")
    for d in os.listdir(gdir):
        if d not in {g["id"] for g in guides}:
            shutil.rmtree(os.path.join(gdir, d))
            print("removed stale guide page", d)
    print(f"{len(guides)} guide pages, {sum(g['hasCover'] for g in guides)} covers, "
          f"{len(regions)} region packs, sitemap {len(urls)} URLs, store id: {sid or '(coming soon)'}")
    if check:
        for g in guides:
            print(f"  {g['id']:15} {'+'.join(g['shelves']):7} places {g['places']:>6}  days {g['days']:>3}  "
                  f"piers {g['piers']:>2}  langs {len(g['languages']):>2}  cover {'yes' if g['hasCover'] else 'name card'}  "
                  f"({g['source']['app']} {g['source']['commit']})")


if __name__ == "__main__":
    main()
