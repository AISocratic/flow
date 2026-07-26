# Flow — Agentic Company OS

System design spec for Flow, a product of **AISocratic**.

## Contact

Project / licensing contact: **fed@aisocratic.org**

Use this address anywhere the project needs a contact — commercial licensing
enquiries, Corporate CLA requests, README and CONTRIBUTING footers. It appears
in `README.md`, `CLA.md` and `CONTRIBUTING.md`; keep all three in sync.

(Not `fed@flowai.xyz` — that was the earlier address and has been replaced.)

## Build

`flow.html` is **generated**. Never edit it directly — edit the pieces in `src/`
and rebuild.

```sh
./build.sh     # assemble src/ -> flow.html
./serve.py     # dev server on :8000, watches src/, rebuilds, live-reloads
```

`build.sh` concatenates `src/head.html`, `src/styles.css`, `src/defs.html` and
`src/sections/*.html` (filename order), then inlines assets:

- `{{IMG:name}}` → `src/images/`, base64 data URI. Photographic PNGs over 400 KB
  are transcoded to JPEG q82 (capped at 1920px wide) — base64 adds ~33%, and the
  raw art would otherwise put megabytes into a single-file document.
- `{{FONT:name.woff2}}` → `src/fonts/`, base64 data URI.

The output is fully self-contained: no network requests, opens offline.
Placeholders work in `styles.css` too, since substitution runs over the whole
assembled file.

## Design language

Type from **aisocratic.org**: Space Grotesk (sans) + JetBrains Mono (mono),
shipped as variable woff2 and inlined.

Layout and colour from **primeintellect.ai**: `#0e0e0e` ground, `#f4f4f4` ink,
`#2a2a2a` hairlines, square corners everywhere (`--radius: 0`), `FIG.n` plate
stamps, dim mono section indices, mono-numbered spec lists, dot-matrix panel
grounds, shared-hairline tile grids.

Specifics worth preserving:

- **Chromatic aberration is deliberate.** Red/cyan text-shadow split on titles
  (aisocratic.org's hero effect), and zero-blur `drop-shadow()` pairs on diagram
  and sparkline SVGs. Disabled in print. Do not "clean this up".
- **Acid lime `#d7ea3f` is structural only** — rules, list markers, link hovers.
  Never inside a diagram, where it would read as a fifth actor role.
- **Actor roles** map to Prime Intellect's chart palette: human `#8b7cf6`, agent
  `#85ed75`, system `#a3a3a3`, data `#f3bc56`, bad `#fb7185`.
- **The hero "The goal" block** is deep violet `#6d5fd0`, not `#8b7cf6` — white
  body copy only clears 3.3:1 on the lighter shade, 5:1 on this one.
- **`.dg rect { rx: 0 }`** squares off SVG nodes via CSS geometry properties,
  overriding the `rx="9"` attributes in markup. No markup changes needed.
- Figures break out of the prose column: `width: min(1320px, 100vw - 56px)`.
  Section rules match that width, not the 880px prose width.

### Chart labels

Every `<text>` must sit inside its node's border. JetBrains Mono sets wide, so
this is easy to break. To audit after changing type or copy, run in the browser:
measure each text's `getBBox()` against its containing `rect` and report any
where the text extends past the box. Fix by widening the node (preserving its
centre), not by shrinking type below ~9px.

## Licence

**AGPL-3.0** + a Contributor License Agreement (`CLA.md`) that grants AISocratic
relicensing rights, which is what makes commercial dual-licensing possible.

Two standing caveats:

- `CLA.md` carries an unreviewed-by-counsel banner. It must be reviewed by a
  lawyer before the first outside contribution is merged.
- `NOTICE` **excludes the hero artwork** (`city.png`, `city2.png`, and the
  `harness`/`memory` jpegs) from the AGPL grant — we may not hold rights to
  license it. Resolve provenance before the repo goes public.

## Repo

`git@github.com:AISocratic/flow.git` — currently **private**, default branch
`main`. The spec is not served anywhere yet; GitHub Pages would need the repo to
be public.
