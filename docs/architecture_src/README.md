# docs/architecture.pdf — how it is built

`architecture.html` is the single source of the Box 9 PDF; `docs/ARCHITECTURE.md` carries the same content as text.
Rebuild after any change (headless Chromium, A4 landscape, 2 pages):

```
chrome --headless --no-sandbox --disable-gpu --no-pdf-header-footer --print-to-pdf=docs/architecture.pdf docs/architecture_src/architecture.html
```

The controller, hardware and CAD blocks state their owners. Their detailed diagrams (Stateflow chart, hardware block
diagram, CAD exploded views) are the owners' contributions and are not invented here.
