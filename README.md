# Pixel Pantry

A recipe shelf for one kitchen. Share a recipe link from your phone and get a clean, ad-free page to cook
from, with ingredients weighed in grams and a one-step-at-a-time method. It runs in a single container on a
box at home and keeps your recipes as plain Markdown files.

## What this is, and isn't

I built this for my own house because I was tired of cooking from a phone that dims, scrolls past the
recipe, and plays a video over the one step I needed. It is tailored to how I cook: by weight, from a
propped-up phone, with a shopping list my family shares and a receipt printer in the kitchen. Those are my
needs; they may not be yours.

It is not a product. There is nothing to sign up for, nothing to pay for, no hosted version, no telemetry,
and no plan to add any. I'm publishing it because other people seem to want the same thing and it's easier
to point at a repo than to describe it. If it suits you, run it. If it almost suits you, fork it; MIT.

What it talks to, completely:

- **The recipe page you paste.** Fetched once, parsed, and the recipe plus its hero image are saved locally.
  The fetch identifies itself as a phone browser, because many recipe sites refuse anything else. Sites
  that still refuse are handled by the optional phone app, which loads the page on your phone and hands the
  HTML to your server.
- **Anthropic's API, only if you add your own key.** Used for pages with no machine-readable recipe, and to
  estimate a weight the table doesn't know. Without a key those features are simply off.
- **Your Press print service, only if you point it at one.**

That's the whole list. No fonts from Google (they're in the repo), no analytics, no update checks.

## What it does

- **Share a link, get a recipe.** The recipe is pulled from the page's schema.org data and saved as a
  Markdown file with YAML front matter. Your recipes are files in a folder; back up the folder.
- **Cook mode.** Ingredients as a checklist with serving scaling; the method one step at a time, or all at
  once, with timers you tap in the text; the screen stays awake.
- **Everything in grams.** Each ingredient line gets a weight next to the cups and spoons, from USDA data.
  Spices are left alone on purpose. Details under Weights below.
- **The basket.** A shopping list shared by every device in the house, grouped by aisle.
- **Paper.** One tap prints a recipe or the basket on a kitchen receipt printer, through a small companion
  service called Press.
- **Installable.** A small PWA with an optional Android share-sheet app.
- **Looks like a game.** A pixel font, sprites, wood and parchment. That part is pure taste.

## Run it

You need a box that stays on with Docker on it: a Raspberry Pi, a NAS, a mini PC, a small VPS.

```sh
git clone https://github.com/timzilla/pixel-pantry.git
cd pixel-pantry
docker compose up -d --build
```

Open `http://<that box>:8095`. Recipes land in `data/recipes/`, hero images in `data/images/`, the basket in
`data/shopping.json`. Nothing else is written anywhere.

Optional settings go in a `.env` file next to the compose file:

```
ANTHROPIC_API_KEY=sk-ant-...     # enables the Claude fallbacks described above; your key, billed to you
PRESS_URL=http://press:8096      # a Press print service; the Print buttons go live
```

### Before you expose it to the internet

1. **Phone features need HTTPS.** Installing the app, the share target and the wake lock only work from a
   secure origin. Plain `http://192.168.x.x` gives you the website, not the app. A Cloudflare tunnel,
   Tailscale, or Caddy with a real certificate all work; I use a Cloudflare tunnel.
2. **There is no login.** Pixel Pantry trusts whoever can reach it: anyone on the URL can add and delete
   recipes and edit the basket. Put it behind something that asks for a password (Cloudflare Access,
   Authelia, Tailscale, basic auth on your reverse proxy) or keep it on your home network. I run it behind
   Cloudflare Access and had no reason to build a second login.

## The phone app (optional)

Many recipe sites refuse requests from servers but happily serve a phone. The `android/` folder is a tiny
(about 20 KB) Android app that appears in the share sheet, loads the shared page in the phone's own browser
engine, and posts the finished HTML to your server at `/add-html`. To build it:

```sh
echo https://pantry.example.com > android/.server        # your server's public address
ANDROID_SDK=/path/to/sdk android/build.sh                # needs Docker; SDK with build-tools 34.0.0 + platforms/android-23
```

The script generates its own signing key the first time (keep `android/.signing/`; updates must use the
same key). Install `android/out/kitchen.apk` on the phone, or let the site serve it at `/kitchen.apk`.
There is no iOS app; the PWA works on iOS for cooking, without the share target.

## Weights

Cups and spoons are a guess; a scale is not. Pixel Pantry weighs every ingredient it can and shows the
grams beside the original amount, so a recipe written in cups can be cooked by weight and scaled honestly.
Hover any weight to see where the number came from.

How a line gets its weight, in order:

1. **Written in weight already** (8 oz, 1 lb, 250 g): converted directly.
2. **The weight table**, `app/weights.json`: about 560 ingredients and 2,900 ways of writing them, each with
   grams per cup, per piece (small, medium, large where it matters), per named unit (clove, stick, slice,
   bunch, sprig, can, jar...) and a density for millilitres. The longest matching phrase wins, so "green
   onion" is not "onion" and "cream cheese" is not "cream". Nearly every number is a USDA FoodData Central
   household measure (SR Legacy and FNDDS, public domain); a few baking staples follow King Arthur's chart,
   and the rest are marked as typical values. Can and package sizes written in the line are used as written.
3. **Spices and dried herbs are never weighed.** A teaspoon of cumin is a teaspoon of cumin.
4. **Claude, only if a key is set**, estimates anything left and the page shows those with a tilde: ~200 g.

The table is a plain JSON file. Add an entry and restart; every recipe on the shelf is re-weighed on startup.
Corrections with a source are welcome. Kosher salt is set to Morton's 4.8 g per teaspoon; Diamond Crystal
users want 2.8 g, and the tooltip says so.

## Printing

A cheap 80 mm thermal receipt printer in the kitchen, the kind shops use, prints a recipe as a strip with
ingredients, grams and numbered steps, or the basket as a checklist grouped by aisle. Paper doesn't lock,
dim, or mind butter.

Printing goes through Press, a companion service that owns the printer and takes print jobs over HTTP from
anything in the house. Set `PRESS_URL` and the Print buttons go live; until then they explain what they
need. Press isn't published; it may be some day, and this README would link to it. If you have your own
print path, `POST /r/<slug>/print` and `POST /list/print` are where the buttons go.

## How it works

`app/main.py` is a small FastAPI service, about a thousand lines in all. `extract.py` uses
[recipe-scrapers](https://github.com/hhursev/recipe-scrapers) to read the page's structured recipe data,
with Claude as a fallback when there is none and a key is set. `parse_ingredient.py` turns "2 cups flour,
sifted" into quantity, unit, name and note; `weights.py` turns that into grams. `store.py` keeps recipes as
files. `app/static/` is the look: a self-hosted pixel font, sprites drawn in `pixel.js`, and a service worker.

Pixel Pantry fetches pages you would read anyway and keeps a copy for your own cooking. It is a personal
tool; please be decent to the sites you pull from.

## Status

It works for one household and is young: first built in early November 2026, in daily use since. Expect rough edges: the ingredient parser is regexes,
the weight table is as good as its entries, and the UI is sized for one phone and one tablet. I'll fix what
I hit. Issues are welcome; pull requests more so, especially weight-table corrections with a source.

## Credits

Fonts: [Pixelify Sans](https://fonts.google.com/specimen/Pixelify+Sans) and
[Jersey 15](https://fonts.google.com/specimen/Jersey+15), both under the SIL Open Font License (copies in
`app/static/fonts/`). Recipe parsing by recipe-scrapers. Ingredient weights from USDA FoodData Central.
Written with Claude Code, which I say up front because people ask.

MIT licensed. Copyright 2026 timzilla.
