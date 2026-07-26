# Flow system design — sources

`flow-system-design.html` (repo root) is **generated**. Edit the pieces here, then run:

```sh
./build.sh
```

## Layout

- `head.html` — `<meta>` + `<title>`
- `styles.css` — all CSS (inlined into a `<style>` block at build time)
- `defs.html` — shared SVG arrow-marker defs
- `sections/` — one file per document block, concatenated in filename order:
  - `00-hero.html` — title, lede, legend, master-loop diagram
  - `01`–`15` — the numbered spec sections
  - `16-flywheel.html`, `17-outro.html` — closing panel, harness figure, footer
- `images/` — figures referenced as `{{IMG:name.jpeg}}` placeholders in sections;
  the build inlines them as base64 data URIs so the output stays a single
  self-contained file.

To add a section, drop a new `NN-name.html` file in `sections/` (a top-level
`<section class="comp">…</section>` indented two spaces) and rebuild.
