# Static assets and the conventions taken from the Vere Novo site

The frontend follows `fabioguida/verenovo-site` (local copy under
`VERENOVO/WEBSITE/.../site/`). What was taken and what was deliberately left out.

## Taken

- **Palette and type variables** under `:root` in `css/styles.css`: ink, navy, paper, text, muted, line,
  accent yellow, the on-dark pair. Same hex values as the site.
- **Fonts**: Archivo (display), Instrument Sans (body), IBM Plex Mono (labels and numbers),
  self-hosted in `fonts/` with their OFL licence files, loaded with `font-display: swap` and one
  preload. Michroma (the site's wordmark font) is not used.
- **Nav**: sticky, dark, blurred, with a `MENU` button and a full-width link list on phones.
- **Buttons**: `.btn` yellow with 2 px radius, `.btn.ghost` outlined.
- **Labels**: `.eyebrow` mono uppercase tracked, `.mono` for numbers with tabular figures.
- **No inline scripts**: every behaviour lives in `js/app.js`, so the site's content-security
  policy can be reused at deploy time.
- **No CDN**: HTMX is served from `js/htmx.min.js` (2.0.4, from unpkg, unmodified).
- **Breakpoints**: 640 px for the nav and container gutter, 520 px for two-column grids.

## Left out

- The marketing layout: hero, marquee band, chapters, people cards, the vertical wordmark strip.
- The animated SVG figures (`wire.js`, `figures.js`, `scurve.js`).
- The static build script: pages here are Jinja templates rendered by FastAPI.

## Added for this app

- `--ok` (green) and `--over` (red) for the balance bars (phase 3).
- Form controls at 48 px minimum height for thumbs; `.riga` item rows; `.totali` grid.
