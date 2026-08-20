# adclip execution roadmap

**Status:** active execution order  
**Updated:** 2026-08-20

This roadmap prioritizes making the existing creative and learning system durable before widening the product further. `STANDALONE_ARCHITECTURE.md` remains the architectural contract; this document is the execution order.

## Governing sequence

```text
release integrity
  -> authoritative local state (S1)
  -> brand/source intelligence (S2)
  -> controlled experiment generation
  -> durable jobs
  -> local workbench
  -> broader performance connectors
  -> guarded activation
```

The reason for this order is structural: adclip already has enough generation and learning capability to justify a product shell. Adding more channels before state, provenance, and brand context are durable would increase migration debt without improving the core learning loop as much.

## R0 — release integrity — in progress

This is a prerequisite, not a product milestone.

- [x] Describe adclip as a marketing creative and learning engine rather than an MCP-only static-ad tool.
- [x] Bound the MCP dependency to the proven compatible major version (`mcp>=1.2,<2`) until MCP 2.x compatibility is explicitly implemented and tested.
- [x] Move the installed CLI entry point to a composition module so new standalone product surfaces can be added without coupling them to the legacy creative CLI module.
- [x] Bump the package development version to `0.2.0` for the current expanded surface.
- [ ] Validate a clean source install on Windows, macOS, and Linux with the declared dependency bounds.
- [ ] Publish a new package release only after the S1/S2 foundation is validated on a clean checkout.

## S1 — authoritative local state

### S1A — persistence substrate — implemented in this slice

- [x] Platform-aware local data directory with `ADCLIP_DATA_DIR` override.
- [x] `ADCLIP_DB_PATH` override for isolated/test deployments.
- [x] SQLite bootstrap using foreign keys, WAL, and forward-only schema migrations.
- [x] Schema migration ledger.
- [x] Global SHA-256 content-addressed artifact store.
- [x] Artifact metadata registry in SQLite.
- [x] `adclip storage status` and `adclip storage migrate` diagnostics.
- [x] Tests that never touch a developer's real local database.

### S1B — migrate existing adclip state — next

Make SQLite authoritative for existing product state while preserving campaign folders as portable projections.

- [ ] Campaign registry keyed by existing stable `cmp_...` IDs.
- [ ] Creative/artifact records keyed by artifact-bound `crv_...` IDs.
- [ ] Email campaign/message records with structured source documents authoritative over rendered HTML/text.
- [ ] Deployment records.
- [ ] Performance observations including attribution context.
- [ ] Experiment records and evidence thresholds.
- [ ] Provider/model/route/prompt-version/generation-parameter provenance per generated asset.
- [ ] Import current campaign-directory JSON into SQLite without changing stable IDs.
- [ ] Export SQLite state back into the current transparent portable campaign layout.
- [ ] Round-trip tests: legacy folder -> database -> portable export preserves identity and evidence semantics.
- [ ] Remove direct file-store writes from new application workflows once repository parity exists.

### S1C — persistence configuration

- [ ] Persistent provider profiles rather than environment-only configuration.
- [ ] Database backup/restore command.
- [ ] Explicit schema compatibility/version diagnostics.
- [ ] Recovery behavior for interrupted migrations.

### S1 definition of done

S1 is complete when SQLite is authoritative for mutable application state, binary artifacts are content-addressed, existing campaign bundles can be imported/exported without identity loss, and no new workflow needs to invent its own persistence format.

Durable execution jobs are intentionally scheduled after S2 and controlled-generation work below; they use the S1 storage substrate but are a separate execution concern.

## S2 — BrandKit and SourceLibrary

Brand context is structured domain state, not one prompt blob.

### S2A — persistent brand/source domain — implemented in this slice

- [x] Persistent `BrandKit` with stable `brd_...` ID and human-readable slug.
- [x] Brand voice state: tone, preferred terms, prohibited terms, style notes.
- [x] Brand visual state: colors/tokens, typography, logo artifact URI, visual notes.
- [x] Persistent `ProductProfile` records with value proposition, audiences, offers, and metadata.
- [x] Persistent `SourceRecord` records with source kind, URI/artifact URI, rights, provenance, and SHA-256.
- [x] Local file sources imported into the shared artifact store.
- [x] Persistent `ClaimRecord` with approved/restricted/rejected/unreviewed status.
- [x] Claim-to-evidence source links.
- [x] Cross-brand product/evidence ownership checks.
- [x] Portable full brand snapshot from the repository layer.
- [x] Standalone CLI for creating/listing/showing brands and adding products, sources, and claims.

### S2B — ingestion and extraction — next

- [ ] Website/page ingestion into SourceLibrary with retrieval timestamp and original URL.
- [ ] Local file ingestion for common text/document/image formats.
- [ ] Editable extraction of brand voice and visual cues from sources.
- [ ] Product-page extraction into candidate product profiles.
- [ ] Review/testimonial ingestion that preserves exact source text and provenance.
- [ ] Candidate claim extraction with default `unreviewed` status.
- [ ] Claim substantiation workflow: evidence must be explicit before promotion to `approved`.
- [ ] Rights/provenance review workflow for imported assets and text.
- [ ] Duplicate-source detection by URI and content hash.

### S2C — campaign grounding — after ingestion

- [ ] CampaignBriefV2 references `brand_id` and one or more `product_id` values.
- [ ] Campaign can explicitly select source IDs and approved claim IDs.
- [ ] Prompt/context assembly reads from BrandKit/SourceLibrary instead of duplicating brand facts into each brief.
- [ ] Generated copy records which claims/sources informed it.
- [ ] Creative artifacts record brand/source lineage in provenance.
- [ ] Policy checks distinguish approved, restricted, rejected, and unreviewed claims.
- [ ] Message-match checks compare ads/email against selected landing-page sources.
- [ ] Portable campaign exports include the minimum referenced brand/source snapshot required to interpret the campaign offline.

### S2 definition of done

S2 is complete when a user can onboard an actual brand, import the evidence and assets that describe it, review extracted products/claims, and create a campaign grounded in that persistent context without manually restating the company in every brief.

## S3 — controlled experiment generation — promoted ahead of UI/connectors

This work closes the loop between the existing experiment evaluator and creative production.

- [ ] Canonical creative-attribute schema for hooks, offers, proof, CTA, visual treatment, format, and other controlled axes.
- [ ] Extract/audit attributes from existing creatives.
- [ ] Generate a treatment from a control while locking non-tested attributes.
- [ ] Reject or downgrade `controlled_single_factor` when the resulting diff changes undeclared factors.
- [ ] Persist the intended factor lock and the observed attribute diff with the experiment.
- [ ] Produce the next treatment directly from the deterministic next-test recommendation.

This comes before more performance connectors because Meta is already sufficient to validate the learning architecture; the larger gain is making adclip capable of manufacturing the next controlled test correctly.

## S4 — durable jobs

- [ ] Persistent job records for generation, ingestion, and synchronization.
- [ ] Frozen provider/model/route/config snapshot before execution.
- [ ] Idempotency keys.
- [ ] Checkpoints and partial completion.
- [ ] Retry policy.
- [ ] Cancellation.
- [ ] Resume after process restart.
- [ ] Progress/event stream usable by CLI and future HTTP/UI.

## S5 — local workbench

Only build the workbench after S1/S2 application state is authoritative.

- [ ] `adclip serve` local HTTP runtime.
- [ ] Brand/source/product/claim management screens.
- [ ] Campaign planning and source selection.
- [ ] Creative variant gallery and controlled-diff view.
- [ ] Email block review/edit experience.
- [ ] Performance and experiment views.
- [ ] Job progress, approval, rejection, and regeneration.
- [ ] Provider configuration and health checks.

## S6 — broader observation connectors

- [ ] Google Ads performance adapter.
- [ ] TikTok Ads performance adapter.
- [ ] ESP/email performance adapters.
- [ ] Explicit, auditable cross-platform metric/action mapping.
- [ ] Scheduled synchronization using S4 durable jobs.

## S7 — guarded activation

- [ ] Separate activation authorization policy from network/read/generation policy.
- [ ] Draft/paused campaign creation only for first write slice.
- [ ] Full launch diff and human approval token.
- [ ] Budget/account/objective/audience/placement/schedule checks.
- [ ] Idempotent publish/pause/rollback.
- [ ] Immutable deployment audit trail.

## Explicitly deprioritized until S1/S2 are solid

- Additional generation-model breadth for its own sake.
- More ad-platform connectors beyond what is needed to prove the abstraction.
- UI-specific persistence.
- Autonomous ad spend.
- A general-purpose design or video-editing surface.

The near-term objective is not to make adclip wider. It is to make the existing campaign -> creative -> observation -> experiment loop durable, brand-grounded, and safe to build a product on top of.
