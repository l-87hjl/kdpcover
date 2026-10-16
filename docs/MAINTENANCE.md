# Maintained fork workflow and private-content boundary

## Branches and review

`upstream-tracking` is a clean copy of the original upstream default branch. Update it
only deliberately and by fast-forward after fetching. It carries no fork documents or
fixes. `main` is the maintained branch, reached through reviewed short-lived fix/update
branches; do not rewrite it. Preserve the legacy `master` branch/default where present.
These are workflow conventions: no GitHub protection, visibility or permission setting
is changed by this patch. Optional local hooks are bypassable and are not remote policy.

Before an update, record both heads and the prior tested pin; fetch upstream; inspect the
whole change; test it on `codex/upstream-<version>`; rerun synthetic and rendered checks;
review the exact resulting diff. Merge by reviewed PR only. Keep the previous pin usable.
A second fork does not remove merge conflicts and adds another synchronization step.

## Inputs, outputs and egress

Keep real manuscript, cover, settings, intermediates, PDFs and logs in explicitly chosen
local private storage outside every Git worktree and public fork. Example location:
`~/PrivatePublishing/paperback/` (choose a nonsynced private location yourself). Do not
copy them into this repository, even temporarily. This task does not create that project
or authorize an agent to read real assets. A future separate private project could combine
interior/cover settings and validation, but remains documentation-only here.

The maintained build guards require an external private root. The synthetic exception is
limited to exact reviewed fixture bytes, not an arbitrary file labeled synthetic. Resource
validation and layout checks still apply. Builds use no-shell TeX and no model/API client.
Inspect changes for network paths; run in an OS/network-isolated environment when stronger
containment is needed. These checks are not a network sandbox and cannot constrain an
arbitrary executable, malicious TeX, another upload tool or future unreviewed code.

## Staging and publication checks

1. Inspect `git status --short`, the intended diff, and the exact changed paths.
2. Stage only explicit paths: `git add -- path/to/source path/to/test`.
3. Run `python3 scripts/publication_preflight.py --staged`.
4. Review `git diff --cached --stat` and the full staged diff, including allowlist changes.
5. Before publication run `python3 scripts/publication_preflight.py --range <public-base>..HEAD`.
   The range scan includes each commit, detecting an unsafe file added and later deleted.
6. Obtain the applicable review/publication authority; verify the published ref and PR.

The exact `.publication-allowlist.json` admits source paths and known upstream assets.
Binary assets and public synthetic fixture bytes are hash-checked. New paths/hashes require
explicit review; editing an allowlist cannot certify content safe. Never stage private
input to test the validator: use throwaway repositories and synthetic negative cases.

Optional per-clone hooks can be enabled manually with
`git config --local core.hooksPath .githooks`; this patch does not enable them globally or
silently change an existing hooks path. The pre-push hook blocks direct main/master
pushes and checks proposed source ranges. Hooks do not cover GitHub/API writes.

`.gitignore` does not protect already tracked files, past Git history, arbitrary prose
inside an allowed source/document, force-added files by itself, bypassed hooks, another
repository or API transmission. If real private content is encountered, stop publication;
do not paste it into an issue/report or rewrite remote history without separate authority.

## Production pins and evidence

Production uses an exact reviewed commit or immutable tested tag, never a moving upstream
branch. Record code SHA, template/filter/font hashes, installed tool/package versions,
settings, page count and final PDF hash privately. Preserve a finished book's source,
settings and artifact; do not overwrite its lock or regenerate it on an upstream update.
Tool/font updates can change layout even with unchanged code and require regression QA.

Local `paperback-candidate-*` tags identify tested candidates, not releases or user
approval. Never move a tag. An update gets a new pin. Roll back by reverting the reviewed
PR or selecting the prior tested pin, without force push or deleting unique work.

## Validation

Use `python3 -m unittest discover -s tests -p 'test_*.py'` and any repository-specific
Node/render checks documented below. Only synthetic fixtures are permitted. Keep all
rendered evidence outside the repository. A successful compilation alone does not prove
text preservation, safe areas, print quality or KDP acceptance.

## Maintained cover behavior

The corrected upstream grid is preserved. `paper=cream` (default) uses .0025 inches
per page; `paper=white` uses .002252. `pages=` must be a positive integer; counts
below 24 are diagnostic-only warnings, and supported stock maxima are checked.
`pdf=` uses engine page-count primitives, not qpdf or shell escape. pdfTeX/XeTeX/
LuaTeX support is exercised where installed; another engine must use explicit pages.

Spine text/logo are omitted below 80 pages, and text must fit the physical spine with
.0625-inch clearance on each side. Text sizing never silently passes a collision:
measured title/author/blurb/back-copy boxes shrink to their documented minimum or
produce an error. Long titles may therefore require shortening/custom layout.
Back copy stops above the reserved lower-back barcode region. No barcode is fabricated;
KDP can add one. `putVersion` prints only the supplied metadata; automatic Git shell
execution was removed. The upstream publication job is disabled for this fork.

Use `python3 scripts/cover_build.py --private-root <external-root> --source <cover.tex>`
for guarded local production-path compilation. Its no-shell compiler is not a sandbox
against arbitrary malicious TeX. Only trusted source is allowed. Real cover source/art
and resulting PDFs/logs remain external to Git. The separate combined publishing
project remains documentation-only.

Run `python3 tests/render_regression.py --output <external-directory>` using already
installed TeX, Poppler and PyMuPDF. Compile success is not KDP acceptance. Preserve
stock, trim, actual interior page count and rendered output hash with the production pin.

[layout finding, 2026-10-16] Multiplying a tiny TeX dimension per page introduced
measurable rounding (white stock was about .0012 inches off at 200 pages). The
maintained class multiplies decimal inches before converting to a TeX length;
rendered stock-size regression checks cover the result.

## CI boundary

The public-content workflow runs only source/guard tests on reviewed synthetic data;
it installs no rendering toolchain and uploads no book/artifact. Local rendered QA is
still required before a candidate pin. CI runs after publication and cannot undo an
accidental disclosure, so explicit staging/pre-push review remain essential. Existing
upstream-owned deployment jobs are not activated for maintained-fork builds.


## Reviewed repair controls

The guarded source must begin with one literal `kdpcover` documentclass and exactly
one active `pages=` or `pdf=` option. Comments cannot supply options; duplicate,
mixed, macro-based or pre-supplied options are rejected. The class reports its actual
page count and the guard verifies it before retaining the output. This trusted-source
subset deliberately rejects unsupported TeX indirection rather than guessing.

Graphics must resolve to one existing PDF/PNG/JPEG file within private storage and
outside Git. Extensionless references are supported only when unambiguous. The checked
private copy uses canonical explicit filenames; source-directory searches cannot select
a different image. Output/sidecars use exclusive no-follow creation and held descriptors.
Text fitting checks both typeset line widths and block height at the chosen font size;
content that cannot fit at the minimum becomes a class error, including direct use.
Historical candidate tags are unchanged; repairs are identified by new exact commits.
