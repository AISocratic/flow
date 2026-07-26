# Contributing to Flow

Thanks for wanting to help. A few things to know before you open a pull request.

## The CLA

Flow requires every contributor to agree to the [Contributor License
Agreement](CLA.md) before their first contribution is merged.

This is not boilerplate — it is what keeps the dual-licensing model working.
Flow is published under the AGPL for everyone, and offered under a separate
commercial licence to organisations whose policies forbid the AGPL. That second
licence is only possible if AISocratic holds the rights to relicense the whole
codebase. Once a project accepts outside contributions without a CLA, it can
never relicense without tracking down every contributor.

You keep full ownership of anything you write. The CLA grants us a licence; it
does not take your copyright, and it does not restrict what you do with your own
work elsewhere.

**To sign:** open a pull request. An automated check will post a one-time
prompt asking you to confirm agreement; replying to it signs the CLA against
your GitHub account for all future contributions. Contributing on behalf of an
employer? Email <fed@flowai.xyz> for a Corporate CLA first.

## Working on the spec

The system design document is generated. **Do not edit `flow.html` directly** —
it is a build artifact and your changes will be overwritten. Edit the pieces in
`src/` and rebuild:

```sh
./build.sh          # assemble src/ -> flow.html
./serve.py          # dev server on :8000, watches src/ and live-reloads
```

`src/README.md` describes the layout.

## Pull requests

- One concern per pull request. A PR that restyles the document *and* changes
  the orchestrator design is two PRs.
- Match the surrounding code. The stylesheet comments explain *why* a rule
  exists, not what it does — keep that habit.
- If you change anything visual, say what you checked it against. Screenshots
  help.
- Run `./build.sh` and commit the regenerated `flow.html` alongside your `src/`
  changes, so the artifact never drifts from its sources.

## Third-party assets

Be careful about adding fonts, images, or icons. Anything you add has to be
licensed compatibly and attributed in `NOTICE`. If you are not certain you have
the right to contribute an asset, don't — open an issue and ask instead.
