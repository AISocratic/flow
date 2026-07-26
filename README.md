# Flow — Agentic Company OS

Goals become projects. Projects become cards. Cards become merged code. Code
moves the metrics. Metrics reshape the goals.

Flow is an operating loop where a fleet of AI agents does the running —
planning, building, verifying, shipping, monitoring — and humans set direction,
review where they choose to, or simply observe. It runs on the AI subscriptions
you already pay for rather than metered API credits.

**[Read the system design →](flow.html)**

## This repository

`flow.html` is the system design specification — a single self-contained file
with every font, figure and image inlined, so it opens offline with no build
step and no network requests.

It is **generated**. Edit the pieces in `src/` and rebuild:

```sh
./build.sh     # assemble src/ -> flow.html
./serve.py     # dev server on :8000, watches src/, rebuilds and live-reloads
```

See `src/README.md` for the source layout.

## Licence

Flow is licensed under the **GNU Affero General Public License v3.0**. See
[LICENSE](LICENSE).

### What that means in practice

**Using Flow to run your company is unrestricted.** Self-host it, modify it,
point it at your private repositories — internal use triggers no obligation
whatsoever.

**The AGPL does not touch the code Flow writes.** Copyleft covers Flow and works
derived from Flow. It does not cover the output of running it. If a Flow agent
opens a pull request against your proprietary repository, that repository is
entirely unaffected. This is the most common misreading of the AGPL, so to be
explicit: your codebase does not become AGPL by having Flow work on it.

**The obligation is narrow.** If you modify Flow and then offer that modified
version to third parties as a network service, you must make your modified
source available to those users. That clause exists to stop someone selling a
closed fork of Flow as a hosted product — nothing more.

### Commercial licensing

If your organisation's policies do not permit AGPL software, Flow is available
under a separate commercial licence. Contact <fed@aisocratic.org>.

### Contributing

Contributions require agreement to the [Contributor License Agreement](CLA.md),
which is what makes the dual-licensing above possible. See
[CONTRIBUTING.md](CONTRIBUTING.md).

### Third-party assets

The bundled fonts are under the SIL Open Font License, and the hero artwork is
excluded from the AGPL grant entirely. See [NOTICE](NOTICE) before reusing this
repository.
