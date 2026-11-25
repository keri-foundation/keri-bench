# The documentation site

keri-bench's documentation, its write-ups and every committed run's report are published at <https://keri-foundation.github.io/keri-bench/>. The site is built the same way as the [KERI conformance suite's](https://keri-foundation.github.io/keri-conformance-suite/) and the [KERI privacy analysis suite's](https://keri-foundation.github.io/keri-priv-analysis-suite/), with the same theme, so the three read as one family (`this.i` 2j423x8t).

## What it publishes

The site carries the README as its home page, every file under `docs/`, and every markdown file under `results/`, which is each run's `report.md`. Every other file in the repository that a page links to, such as a run's `timeline.jsonl`, `provenance.json` or `report.json`, a scenario or a `SHA256SUMS` manifest, is linked on GitHub instead.

A run report opens with a summary in sentences and gives durations in the units a person reads (`this.i` 6d0jwr9z), but it does not say which write-up it supports. So the site puts a short note at the top of every page under `results/`, set apart from the report: the run's directory, the write-up in `docs/` that cites it, a link to [reading a run report](reading-a-report.md) and one to the [glossary](glossary.md). The report's own text follows unchanged (`this.i` 5gwu92w5). A run's write-up is the one that cites its results directory, preferring the one whose name the directory's starts with.

Most terms in the [glossary](glossary.md) show their meaning on hover wherever they appear on the site (`this.i` 4wnur86k). The exceptions are deliberate: the role words (issuer, holder, verifier and the rest) and other words that fill every page have no hover spelling, because underlining each of them would bury the hovers that help; the glossary page defines them all. The glossary is written once, in `docs/glossary.toml`: `scripts/glossary` writes `docs/glossary.md` from it, a test fails when the committed page is out of date, and the assembler appends each term's spellings to every page as abbreviation definitions, which the site renders as hover text. Milestone names such as `verified` are defined on hover only on run reports, where they are names; in a write-up they are ordinary words.

The site renders only what is committed. It runs no scenario and no adapter, and it does not render results itself: each run's `report.md` is rendered from the run's committed `report.json`, which `keri-bench report` derived from its timeline and provenance, so the site cannot disagree with the report a reader would regenerate. When the renderer changes, `scripts/rerender-reports` renders every committed report again from its `report.json` and updates the `report.md` lines of each `SHA256SUMS`, leaving every other line as it was; tests hold every committed report to the renderer and every manifest line to its file. A push to `main` that changes markdown or results republishes the site without re-measuring anything.

## What the build refuses

`scripts/site-source` assembles the site's markdown into `_site/src` and rewrites each link for that layout. It stops, and the site is not built, when:

- a page links to a path the repository does not have, or to one outside it, or the link goes through a symbolic link;
- a published page, rendered with the site's own markdown extensions, contains an element, an attribute or a link scheme outside a short allow-list (the elements markdown produces, no event handlers, inline style only for table alignment, and links that are relative or use `http`, `https` or `mailto`);
- a published SVG does not parse, declares entities, carries a processing instruction other than the XML declaration, or holds an element or attribute outside the drawing vocabulary a plotting library writes, a link other than a `#` reference, or a stylesheet or `style` attribute that is anything but plain declarations;
- a file under `docs/` would take the place of a generated page (`docs/index.md` or `docs/results/`);
- the output directory exists and the tool did not make it.

The HTML rules exist because a report can carry text a stack supplied, such as a failed stage's error. A report that put markup there would otherwise publish it on this site's origin. The rule refuses the report rather than escaping it, so a committed report and its published page always say the same thing. The check renders the page rather than searching the markdown for tags, because markdown has too many ways to produce markup that a pattern over the source misses. The renderer is the Python-Markdown and pymdown-extensions versions that the pinned Zensical uses, and a test holds the extension list to `zensical.toml`.

The assembler, `tools/site_source.py`, is a near copy of keri-priv-analysis-suite's, kept close so that a fix to one can be carried to the other.

## Building it locally

```bash
uv sync --locked --group site
uv run python scripts/site-source
uv run zensical build --clean --strict
```

The site is then in `_site/html`, which `python3 -m http.server --directory _site/html` serves. Zensical is pre-1.0, so `pyproject.toml` pins it exactly and a newer version is adopted by changing the pin. Its only input is the plain markdown in `_site/src`, so replacing the generator means replacing `zensical.toml` and one build step.

## Deployment

`.github/workflows/pages.yml` runs on every push to `main`. Its build job holds a read-only token. Its deploy job holds the Pages and OIDC permissions and runs no repository code. CI's `site` job builds the same site on every pull request and push without deploying it, so a broken link fails there rather than at the deploy. Pages must be enabled in the repository's settings with GitHub Actions as its source. Otherwise the deploy job stops at its configuration check.
