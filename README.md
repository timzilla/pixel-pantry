# Pixel Pantry

A cozy little recipe shelf for your kitchen. Share a recipe link from your phone and it turns into a clean,
ad-free page to cook from: ingredients you can tick off, weights in grams, one step at a time, and a
shopping list that tells you what to actually buy. All wrapped in a pixel-art kitchen I'm a bit too pleased with.

It runs in one container on a box at home and keeps your recipes as plain Markdown files you own.

## Why I made it

Cooking from recipe websites drove me up the wall: the phone dims mid-step, the recipe is buried
under someone's life story, and a video autoplays right over the one line I need with flour on my hands.
So I built the kitchen companion I wanted, around how my family actually cooks: by weight, from a phone
propped against the flour tin, with a shared shopping list and a receipt printer on the counter.

It turned out to be one of my favorite things in the house, and I think it's too neat to keep to myself.

It isn't a product and I'm not selling anything. There's no account, no hosted version, no subscription,
no tracking, and no plans for any of that. It's a home project I'm proud of and happy to share. If it fits
your kitchen, I hope you enjoy it. If it almost fits, fork it and make it yours; it's MIT licensed. And if
you build something fun on top of it, I'd love to hear about it.

## What it does

- **Share a link, get a recipe.** Pixel Pantry reads the recipe out of the page and saves it as a Markdown
  file. No ads, no pop-ups, no story to scroll past. Your recipes live in a folder, so backing up is copying a folder.
- **Cook mode.** Ingredients as a checklist with serving scaling. The method one step at a time in big
  type, or all at once if you prefer. Tap "10 minutes" in a step and a little hourglass starts counting.
  The screen stays awake while you cook.
- **Everything in grams.** Every ingredient gets a weight beside the cups and spoons, so you can cook on a
  scale and scale a recipe up or down honestly. "2 cups cooked chicken" shows 280 g; "1 large onion" shows
  150 g. Spices are left as spoons on purpose. More on how this works below; it's my favorite part.
- **A shopping list that knows how food is sold.** The basket is shared across every device in the house
  and grouped by aisle. Each line also says what to pick up: "1/4 cup lemon juice" becomes 2 lemons, "400 g
  flour" becomes one 2 lb bag (with about 500 g left over), "3 cups broth" becomes a 32 oz carton, and a
  quarter teaspoon of baking soda gently suggests checking the cupboard before buying a whole box.
- **Paper, if you like.** With a cheap receipt printer in the kitchen, one tap prints the recipe as a
  strip, or the shopping list as a checklist you can take to the store. Paper doesn't dim, doesn't lock,
  and doesn't mind butter.
- **Installs like an app.** Add it to your home screen. On Android there's a tiny companion app so
  "Share → Pixel Pantry" works from any recipe page.
- **Looks like a game.** A pixel font, hand-drawn sprites, wood frames and parchment. Cooking should be fun.

## Run it

You need a small always-on computer with Docker: a Raspberry Pi, a NAS, a mini PC, or a cheap VPS all work.

```sh
git clone https://github.com/timzilla/pixel-pantry.git
cd pixel-pantry
docker compose up -d --build
```

Then open `http://<that box>:8095` and share your first recipe. Recipes are saved in `data/recipes/`,
photos in `data/images/`, and the shopping list in `data/shopping.json`.

A couple of optional extras go in a `.env` file next to the compose file:

```
ANTHROPIC_API_KEY=sk-ant-...     # lets Claude read pages with no recipe data and estimate unusual weights (your key, your bill)
PRESS_URL=http://press:8096      # a Press print service; the Print buttons light up
```

### Before you open it up to the internet

1. **The phone features need HTTPS.** Installing it as an app, the share sheet and keeping the screen
   awake only work over a secure connection. On plain `http://192.168.x.x` you get the website without the
   app. A Cloudflare tunnel, Tailscale, or Caddy with a real certificate all do the trick; I use a Cloudflare tunnel.
2. **There's no login built in.** Anyone who can reach it can add recipes and edit the basket. Keep it on
   your home network, or put it behind something that asks who you are: Cloudflare Access, Authelia,
   Tailscale, or basic auth on your reverse proxy. I use Cloudflare Access, which is why I never built a second login.

### What it connects to

I care about knowing what my own server talks to, so here's the complete list:

- **The recipe page you share.** Fetched once; the recipe and its photo are saved locally. The request
  identifies itself as a phone browser, because a lot of recipe sites turn anything else away. For the
  stubborn ones, the Android app loads the page on your phone and hands it over.
- **Anthropic's API, only if you add your own key.** Used for pages that have no recipe data, and to guess a
  weight the table doesn't know yet. No key, no calls.
- **Your Press print service, only if you set one up.**

That's it. The fonts are in the repo, and there's no analytics and no phoning home.

## The phone app (optional)

Some recipe sites refuse to talk to servers but happily serve a phone. The `android/` folder holds a tiny
(about 20 KB) app that shows up in your share sheet, opens the page in the phone's own browser engine, and
sends the finished page to your Pixel Pantry. To build it:

```sh
echo https://pantry.example.com > android/.server        # your server's public address
ANDROID_SDK=/path/to/sdk android/build.sh                # needs Docker; SDK with build-tools 34.0.0 + platforms/android-23
```

The first build makes its own signing key in `android/.signing/`. Keep that folder, since updates need the
same key. Install `android/out/kitchen.apk` on your phone, or let the site offer it at `/kitchen.apk`.
There's no iOS app yet; on iPhone the installed web app works great for cooking, just without the share sheet.

## How the weights work

Cups and spoons are a guess; a scale is a fact. Pixel Pantry weighs every ingredient it can and shows the
grams next to the original amount. Hover any weight to see where the number came from.

For each ingredient line, in order:

1. **Already a weight?** 8 oz, 1 lb and 250 g are simply converted.
2. **The weight table**, `app/weights.json`: about 560 ingredients and 2,900 ways people write them, with
   grams per cup, per piece (small, medium or large where it matters), per clove, stick, slice, bunch,
   sprig, can and jar, plus densities for millilitres. The longest match wins, so "green onion" isn't "onion"
   and "cream cheese" isn't "cream". Nearly every number is a USDA FoodData Central household measure
   (public domain); a few baking staples follow King Arthur's chart. Can sizes written in the recipe are
   used as written.
3. **Spices and dried herbs stay as spoons.** A teaspoon of cumin is a teaspoon of cumin.
4. **Claude fills the gaps, if you've added a key.** Those weights show with a tilde, like ~200 g.

The table is a plain JSON file. Add or fix an entry, restart, and every recipe on your shelf is re-weighed.
One judgment call to know about: kosher salt uses Morton's 4.8 g per teaspoon; if you're a Diamond Crystal
household, it's 2.8 g, and the tooltip says so.

## How the shopping list knows what to buy

Every basket line gets a "buy" suggestion, worked out a few different ways:

- **Things made from something else** go back to what you buy: lemon juice to lemons, minced garlic to heads of garlic, zest to fruit.
- **Things sold by count**, like onions, avocados, eggs and chicken breasts, become how many to grab, rounded up.
- **Herbs** become bunches.
- **Everything else** becomes the package size US stores stock most. Those come from the USDA's Branded Foods
  data, about 750,000 grocery products with their package sizes, boiled down to `app/packs.json`, with the
  everyday staples checked by hand.
- **Small amounts of pantry staples** say "check the cupboard," because nobody needs a new box of baking soda
  for a quarter teaspoon.

## Printing

A cheap 80 mm thermal receipt printer, the kind shops use, makes a great kitchen companion. Pixel Pantry
prints a recipe as a strip with ingredients, grams and numbered steps, or the shopping list as a checklist
grouped by aisle.

Printing goes through Press, a small service of mine that owns the printer and takes print jobs from
anything in the house. Set `PRESS_URL` and the Print buttons come alive; until then they explain what they
need. Press isn't published yet, and might be one day. If you already have your own way to print,
`POST /r/<slug>/print` and `POST /list/print` are where the buttons send their requests.

## Under the hood

`app/main.py` is a small FastAPI service, about a thousand lines all told. `extract.py` uses the excellent
[recipe-scrapers](https://github.com/hhursev/recipe-scrapers) to read a page's structured recipe data, with
Claude as a fallback when there isn't any and a key is set. `parse_ingredient.py` turns "2 cups flour,
sifted" into quantity, unit, name and note; `weights.py` turns that into grams; `buy.py` turns it into what
to buy. `store.py` keeps recipes as files. `app/static/` is the look: a self-hosted pixel font, sprites drawn
in `pixel.js`, and a service worker.

Pixel Pantry saves recipes from pages you'd read anyway, for your own cooking. Please be kind to the sites
and cooks you pull from; their recipes are why any of this works.

## Where it's at

It's young but loved: built in early November 2026 and in use in my kitchen since. There are
rough edges. The ingredient parser is a pile of regular expressions, the weight and package tables are only
as good as their entries, and the layout is tuned for the phone and tablet in my kitchen. I'm still adding to
it, and I'll keep fixing what I run into.

Issues, ideas and pull requests are all welcome. Corrections to the weight or package tables are especially
appreciated; please include where the number came from.

## Thanks

Fonts: [Pixelify Sans](https://fonts.google.com/specimen/Pixelify+Sans) and
[Jersey 15](https://fonts.google.com/specimen/Jersey+15), both under the SIL Open Font License (copies in
`app/static/fonts/`). Recipe parsing by recipe-scrapers. Ingredient weights and package sizes from USDA
FoodData Central (SR Legacy, FNDDS and Branded Foods), which is a genuinely wonderful public resource.

I built this together with Claude Code. It was a lot of fun to make that way.

MIT licensed. Copyright 2026 timzilla.
