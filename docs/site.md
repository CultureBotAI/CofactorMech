# Static catalogue and Pages procedure

The maintained renderer is `src/cofactormech/site.py`; templates and local assets
live beside it in `site_templates/` and `site_assets/`. It projects the existing
validated `data/cofactors/*.yaml` corpus. It does not curate, normalize or enrich
scientific records. The complete catalogue and every detail page work without
JavaScript; the local script only filters already-rendered rows.

## Build and inspect

```sh
uv sync --locked
just check
just check-vendored
just build-site
just check-site
python -m http.server --directory build 8000
```

Open `http://localhost:8000/site/index.html` and, for example,
`http://localhost:8000/site/records/fad/index.html`. Relative links deliberately
work under this nested route and the eventual `/CofactorMech/` Pages prefix.
YAML downloads live at `build/site/sources/`; the schema and licence are bundled.
All evidence links retain their recorded references, locators and source
licences. Upstream website availability is outside the local site check.

The builder validates the repository, refuses an empty corpus, and checks corpus,
schema and licence bytes against the recorded Git revision before linking to it.
Commit source data changes before building. It sorts inputs and output rows,
uses content hashes rather than wall-clock timestamps, and produces identical
bytes for the same source revision and renderer. `site-manifest.json` binds the
record count, categories, corpus/schema hashes and generated artifact hashes.
`just check-site` checks actual output: complete page count, landmarks, safe URLs,
relative local links/fragments and artifact hashes. Source data and the generated
YAML downloads are byte-identical.

`build/site/` is ignored and disposable. Rebuild only replaces a directory carrying
the renderer's exact marker; an unmarked or symlinked destination is refused.
Do not manually edit output or put retained work there. Retained review evidence
belongs in the repository's ignored `workspace/` or its durable owned work area.

For real browser verification, install Playwright's browser in your chosen durable
work area, then use the committed helper (site runtime has no Playwright dependency):

```sh
uv run --with playwright==1.65.1 playwright install chromium
uv run --with playwright==1.65.1 python scripts/adhoc/verify_site_browser.py \
  --site build/site --evidence workspace/site-browser-review
```

The evidence directory must be new; use another name for a repeat run. An optional
`--executable /absolute/path/to/chromium` uses an existing local browser. The helper
serves locally and saves desktop/mobile/no-JS screenshots, a browser version,
checks, reference-probe status and artifact hashes. It does not deploy or change
records. It covers name/identifier search, categories/reset, no results and markup
queries, keyboard skip/focus/table scroll, no viewport overflow, computed text contrast, nested detail and
source links, claim-reference identity, no-JS content and script/request errors.

## Reuse and applicability

The design adapts fleet interaction/layout decisions with domain-specific text;
it does not introduce a remote UI library or copy an exhaustive fleet list.

| Reader task | Reused source at inspected revision | Local acceptance |
| --- | --- | --- |
| Scan a project | [TraitMech base/index](https://github.com/CultureBotAI/TraitMech/tree/2ccbc22ccfb8bd00c9d9ca70e11e020f818fbc18/src/traitmech/templates) | System font, constrained shell, pastel hero, generated category counts and corpus/schema/licence footer. |
| Find a record | [AntibioticMech class template](https://github.com/CultureBotAI/AntibioticMech/blob/6ec4c26ca0b650f895b4e3d7d642e5d9eb22dda7/src/antibioticmech/templates/class.html) | Labelled name/identifier search, category select, reset and live matching/total count across every static row. |
| Inspect evidence | [AntibioticMech record/macros](https://github.com/CultureBotAI/AntibioticMech/tree/6ec4c26ca0b650f895b4e3d7d642e5d9eb22dda7/src/antibioticmech/templates) | Claim-specific evidence, source versions/locators/licences, research gaps and source-YAML links. |
| Read on mobile and keyboard | AntibioticMech named scroll-region pattern | Semantic table, contained horizontal scrolling, visible focus, skip link and native controls. |
| Move between views/projects | TraitMech relative root-prefix shell | Catalogue/detail/source links work at nested routes; All Mech projects links to the maintained directory. |
| Domain interpretation | Local schema and curated corpus | Keep metal/coenzyme/prosthetic categories; distinguish provisional ingredient links, precursor supply, conjugate forms and scoped verified relationships. |
| Maps, embeddings, sharding, pagination, theme persistence | Not applicable to this initial static catalogue | No paid research, embeddings, network-fetched index, maps or artificial pagination. No existing theme preference is displaced. |

## CI and deployment boundary

`pages.yaml` builds and checks on pull requests, merge groups, main pushes and
manual runs. The `build-site` job has read-only contents permission and uploads a
reviewable `catalogue-site` artifact. It neither configures nor enables Pages.
All actions are pinned to inspected immutable commits. The ordinary strict
workflow continues to run the repository's full required validation.

Publication additionally requires all of:

- Repository variable `PAGES_DEPLOYMENT_ENABLED` equals the exact string `true`.
- The event is a push to main, or a manual run on main with `deploy=true`.
- Successful build/checks and the `github-pages` environment's approval/protection.

Only the deploy job receives `pages: write` and `id-token: write`; it depends on
the build and uses the Pages artifact from that run. Main runs are serialized
with `cancel-in-progress: false`; pull-request runs use separate concurrency
groups. There is no auto-enabling `configure-pages` step. No repository variable,
Pages setting or environment is changed by this implementation.

## Separate operator decision and first deployment

These are instructions for a later explicitly authorized operator, not actions
performed by this preparation PR. Follow [GitHub's custom Pages workflow guide](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

1. Review and merge the exact approved PR head through the repository's normal
   process. Recheck current main, all required checks and the retained site artifact.
2. In repository Settings → Pages, choose **GitHub Actions** as the source. Do not
   enable a branch source or publish an empty directory.
3. In Settings → Environments → `github-pages`, restrict deployments to `main`,
   configure the designated required human reviewer, and disallow self-review
   where available. Confirm the repository visibility and intended public URL.
4. Only after publication approval, set `PAGES_DEPLOYMENT_ENABLED=true` in Actions
   repository variables. This enables future approved-main pushes as well as
   explicit manual main deployments. Leave it unset/false while publication is held.
5. Trigger the exact main workflow:

   ```sh
   gh workflow run pages.yaml --repo CultureBotAI/CofactorMech --ref main -f deploy=true
   gh run list --repo CultureBotAI/CofactorMech --workflow pages.yaml --limit 5
   ```

6. Inspect the exact run's `headSha`, build/check artifact and environment approval;
   approve only the reviewed main revision. Confirm the Pages deployment completes.
7. Verify `https://culturebotai.github.io/CofactorMech/`, a nested record, YAML and
   schema download, search, keyboard/mobile use and no-JS fallback. Compare the
   published manifest's revision, count and hashes with the approved artifact.
   Only then request the separately owned directory website link.

## Rollback

If publication is faulty, set `PAGES_DEPLOYMENT_ENABLED=false` to prevent new
publication attempts and inspect any already-running deployment before acting.
This does not unpublish a site or cancel other work. Preserve the failed artifact,
manifest and run ID. Prepare a normal reviewed revert/fix PR for renderer/workflow
changes; do not revert curated scientific records to repair presentation. After
separate approval, merge, rebuild and verify the corrected main, re-enable the
variable and repeat the manual deployment procedure. Disabling/unpublishing Pages
or cancelling an in-flight deployment requires the operator's explicit decision.
