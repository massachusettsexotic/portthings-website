# portthings.com

The website for **Port Things**, the one iOS app that holds every Things destination guide
(source: `~/ThingsHub`). Static HTML/CSS on GitHub Pages, same setup as tulumthings.com.

**Port Things is not on the App Store yet.** Every page says "Coming soon to the App Store".
No store badge and no prices. The planned prices ($4.99 app with one guide included, $4.99 per
guide, about $9.99 per cruise-region pack, about $19.99 for All guides) live in App Store Connect
and can change, so they stay off the site.

## Build

    python3 tools/build_site.py --check

Reads `~/ThingsHub/ThingsHub/Catalog/catalog.json`, `Packs/manifest.json`, `Packs/<id>.json`
and `Covers.xcassets` (read-only) and writes `index.html`, `guide/<id>/index.html`,
`covers/<id>.png`, `404.html`, `sitemap.xml` and `robots.txt`. Only `status: "live"` guides
appear (Mazatlán and Alaska are hidden). Flip a guide in catalog.json, re-export its pack in
ThingsHub, re-run, push.

- Covers are Dan's art, copied byte-for-byte and then only resized to 360 px (`sips -Z`).
  Guides with `placeholderIcon: true` get a plain name card, as in the app.
- Facts on guide pages (places, ready-made days, cruise piers) are the numbers the app's
  store sheet shows (`manifest.json counts`: venues, dayTrips, piers). Languages, piers, day-plan
  titles, areas and map categories come from the pack. Nothing is typed in by hand.
- Hand-written files: `style.css`, `app-store.json`, `CNAME`, `.nojekyll`,
  `.well-known/apple-app-site-association`.

## Launch day

1. Put the numeric App Store ID in `app-store.json`: `{"PortThings": "1234567890"}`.
2. Re-run the build and push. Pages also read that file when they load, so the badge becomes
   the store link even before a rebuild.

## Universal links

The app claims `applinks:portthings.com` and opens `https://portthings.com/guide/<id>`
(and `/?guide=<id>`, which the home page forwards to `/guide/<id>/` in a browser).
`/.well-known/apple-app-site-association` lists appID `F3933R6J9S.com.ipmma.calc.ThingsHub`,
paths `/guide/*`. `.nojekyll` is required, or Jekyll drops the `.well-known` folder.
GitHub Pages serves the file (no extension) as `application/octet-stream`. Apple's CDN has
accepted that since iOS 9.3 (the file must be unsigned JSON, reachable over HTTPS with no
redirects), so it works once HTTPS is on. Check with:

    curl -sI https://portthings.com/.well-known/apple-app-site-association
    curl -s https://app-site-association.cdn-apple.com/a/v1/portthings.com

## TODO

- **Privacy page.** There is no Port Things privacy page yet. The footer links to
  https://incmpltellc.com/. Add `incmpltellc.com/portthings/privacy.html` (canonical, for App
  Store Connect) and point the footer at it.
- **HTTPS.** After Dan's DNS is in and GitHub's certificate state is `approved`:
  `gh api -X PUT repos/massachusettsexotic/portthings-website/pages -F https_enforced=true`.
  At most one custom-domain re-add per hour (see memory feedback_github_pages_custom_domain_wait).
- **Port Things app icon.** None exists yet (Dan's art). When it lands, use it as the favicon
  and in the guide-page "Get the guide" box.

## Moving the port pages from tulumthings.com (at Port Things launch, not before)

tulumthings.com carries 53 cruise-port pages and 12 hubs at `/<app>/ports/<slug>/`, generated
by `~/tulumthings-website/tools/build_port_pages.py`. They stay there until Port Things is live,
so the two sites never carry duplicate content. On launch day:

1. Port the generator here: output `portthings.com/guide/<id>/ports/<slug>/` (one hub per guide at
   `/guide/<id>/ports/`), with the CTA pointing at Port Things instead of the single app.
2. On tulumthings.com, replace each port page and hub with a redirect stub: `<link rel="canonical">`
   to the new URL plus `<meta http-equiv="refresh" content="0; url=...">` (GitHub Pages has no
   server-side 301s). Keep the stubs forever so old links keep working.
3. Drop the moved URLs from tulumthings.com's `sitemap.xml`, add them to this one.
4. Point the tulumthings.com app pages for guides now inside Port Things at `/guide/<id>/` here.
5. Privacy pages stay on incmpltellc.com (canonical, in the App Store metadata).

## DNS (Dan, at GoDaddy)

Same five records as passthecore.com and tulumthings.com: four `A @` →
185.199.108.153 / 185.199.109.153 / 185.199.110.153 / 185.199.111.153, `CNAME www` →
`massachusettsexotic.github.io`, and delete GoDaddy's "WebsiteBuilder Site" parking A record.
Leave NS/SOA and any MX/TXT alone.
