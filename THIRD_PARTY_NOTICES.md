# Third-party sources, attribution, and retained notices

Tailored's workflow documents are a selection, rewrite, and adaptation of methods
from the projects below. They are not unmodified upstream skills or an official
bundle. Source code, search datasets, media, logos, and the upstream applications
are not included. The scanner, gate, direction roll and punctuation scripts and
their tests come from the project owner's design-review-loop and were written by
the owner.

This project's own contributions are offered under [Apache-2.0](LICENSE).
Upstream copyright and applicable license terms remain in force. These notices
must not be removed from redistributions to which they apply. Attribution alone
does not replace a license grant or the conditions of that license.

| Source | Declared license / retained text | Contribution used here |
|---|---|---|
| [Matt Pocock / skills](https://github.com/mattpocock/skills), grilling | MIT, Copyright (c) 2026 Matt Pocock. [Full notice](licenses/grilling.txt) | Dependency-aware discovery; separation of environment facts and user decisions. |
| [Leonxlnx / taste-skill](https://github.com/Leonxlnx/taste-skill) | MIT, Copyright (c) 2026 Leonxlnx. [Full notice](licenses/taste-skill.txt) | Context-first visual decisions, anti-template discipline, coherent hierarchy and states. |
| [Open Design contributors / OpenDesign](https://github.com/nexu-io/open-design) | Apache-2.0; Copyright 2026 Open Design contributors as stated in its inspected license. [Full text](licenses/open-design.txt) | Design-contract organization, usable artifacts, preview and refinement workflow. |
| [Next Level Builder / UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | MIT, Copyright (c) 2024 Next Level Builder. [Full notice](licenses/ui-ux-pro-max.txt) | Accessibility, touch interaction, context-specific UX lookup and stack verification. |
| [Anthropic / frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design), via OpenDesign | Apache-2.0 as declared for that skill. [Full text](licenses/anthropic-frontend-design.txt) | Product-specific frontend craft and deliberate visual direction, as referenced through OpenDesign. |
| [Impeccable](https://github.com/pbakaus/impeccable) | Apache-2.0. Ideas only; no files or text were copied. | Separating product context from the visual system, scanning for AI-slop after edits, tone adjustments such as "bolder" and "quieter". |
| Project owner's design-review-loop | Written by the project owner and merged into this repository at the owner's request; released under this project's Apache-2.0 license. | Four review principles and scoring anchors, the AI-slop rule table and scanner, two-layer independent review, the gate and round limits, rolling a design direction. |

## Adaptations and new material

The `SKILL.md` and `references/*.md` documents were first adapted on 2026-10-19
and rewritten on 2026-10-26 to cover websites, web apps, dashboards, desktop
tools, mobile apps and AI products. They add concrete craft guidance, visual
directions chosen by looking rather than by questionnaire, real workflow and
data-continuity boundaries, and actual-interaction evidence for working-app
claims, while keeping inherited palette, font, frame, shadow and stack defaults
out.

The integration does not claim ownership of upstream material. In particular,
MIT permission and copyright notices are retained in full even though no upstream
implementation is bundled. Apache-2.0 license copies and attribution are retained
for the Apache-derived methodology. [NOTICE](NOTICE) describes this integration
and its modifications. Any additional upstream file included in a future change
must be audited separately, including its file-specific license and any NOTICE.

## Version records

[licenses/upstream-manifest.json](licenses/upstream-manifest.json) records exact
commits, license paths, license-file SHA-256 hashes and root NOTICE checks from
the public-source verification on 2026-10-19. Original design-method source
snapshots, which may differ from those license-verification snapshots, are listed
in [references/sources.md](references/sources.md). The manifest is not a claim
that every file in an upstream repository uses the same license.

No root NOTICE was present at the inspected commits. This does not infer anything
about uninspected subdirectories or future versions. OpenDesign's frontend-design
entry explicitly identifies Anthropic as its upstream and declares a separate
Apache-2.0 license; that source is credited separately here.

Names are used only to identify sources. No affiliation, endorsement,
certification, trademark rights, or blanket non-infringement warranty is implied.
