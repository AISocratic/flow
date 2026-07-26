#!/usr/bin/env bash
# Flow — Agentic Company OS
# Copyright (c) 2026 AISocratic
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Assemble flow.html from the pieces in src/.
# Usage: ./build.sh
set -euo pipefail
cd "$(dirname "$0")"

out=flow.html
tmp="$out.tmp"

{
  cat src/head.html
  echo '<style>'
  cat src/styles.css
  echo '</style>'
  echo
  cat src/defs.html
  echo
  echo '<div class="wrap">'
  for f in src/sections/*.html; do
    echo
    cat "$f"
  done
  echo '</div>'
} > "$tmp"

# Inline assets: {{IMG:name}} -> src/images/, {{FONT:name.woff2}} -> src/fonts/
# Photographic PNGs are transcoded to JPEG on the way in — base64 adds ~33%,
# and a 2 MB source would otherwise put 2.8 MB into a single-file document.
python3 - "$tmp" <<'EOF'
import base64, io, os, re, sys

INLINE_JPEG_OVER = 400 * 1024   # bytes; above this a PNG gets transcoded
JPEG_QUALITY = 82
MAX_WIDTH = 1920

path = sys.argv[1]
html = open(path).read()

def b64(data):
    return base64.b64encode(data).decode()

def img(m):
    name = m.group(1)
    src = 'src/images/' + name
    raw = open(src, 'rb').read()
    ext = os.path.splitext(name)[1].lower()

    if ext == '.png' and len(raw) > INLINE_JPEG_OVER:
        from PIL import Image
        im = Image.open(io.BytesIO(raw)).convert('RGB')
        if im.width > MAX_WIDTH:
            im = im.resize((MAX_WIDTH, round(im.height * MAX_WIDTH / im.width)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=JPEG_QUALITY, optimize=True, progressive=True)
        out = buf.getvalue()
        print('  %-14s %5d KB png -> %4d KB jpeg' % (name, len(raw) // 1024, len(out) // 1024))
        return 'data:image/jpeg;base64,' + b64(out)

    mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.gif': 'image/gif', '.svg': 'image/svg+xml', '.webp': 'image/webp'}[ext]
    return 'data:%s;base64,' % mime + b64(raw)

def font(m):
    return 'data:font/woff2;base64,' + b64(open('src/fonts/' + m.group(1), 'rb').read())

html = re.sub(r'\{\{IMG:([\w.-]+)\}\}', img, html)
html = re.sub(r'\{\{FONT:([\w.-]+)\}\}', font, html)
open(path, 'w').write(html)
EOF

mv "$tmp" "$out"
echo "built $out ($(wc -c < "$out" | tr -d ' ') bytes)"
