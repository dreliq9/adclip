# BrandKit and SourceLibrary foundation

**Status:** active S2A foundation  
**Storage:** SQLite + content-addressed artifacts

Brand context in adclip is persistent application state. It is not intended to be copied into every campaign brief or collapsed into one unstructured prompt.

## Domain model

```text
BrandKit brd_...
  |
  +--> brand voice
  |      tone
  |      preferred terms
  |      prohibited terms
  |      style notes
  |
  +--> brand visual
  |      colors/tokens
  |      typography
  |      logo artifact URI
  |      visual notes
  |
  +--> ProductProfile prd_...
  |      value proposition
  |      audiences
  |      offers
  |
  +--> SourceRecord src_...
  |      source kind
  |      URI or artifact:// URI
  |      rights status
  |      provenance
  |      SHA-256 when local content is stored
  |
  +--> ClaimRecord clm_...
         approved | restricted | rejected | unreviewed
         evidence source IDs
```

Sources and claims may optionally attach to one product inside the brand.

## Local storage

By default, adclip stores application data in a platform-appropriate local data directory:

```text
Windows: %LOCALAPPDATA%/adclip/
macOS:   ~/Library/Application Support/adclip/
Linux:   ${XDG_DATA_HOME:-~/.local/share}/adclip/
```

Layout:

```text
adclip.db
artifacts/
  sha256/
    aa/
      bb/
        <full sha256>
```

Overrides:

```text
ADCLIP_DATA_DIR
ADCLIP_DB_PATH
```

`ADCLIP_DB_PATH` is useful for tests, isolated workspaces, and portable validation. Application tests should always use a temporary database rather than a developer's real local state.

Inspect storage:

```bash
adclip storage status
adclip storage migrate
```

## Create a brand

```bash
adclip brand create \
  --slug morrow \
  --name "Morrow" \
  --description "Simple daily skincare" \
  --website-url https://example.com \
  --tone "calm,specific,low-hype" \
  --colors "#F6F1E8,#1F2937"
```

List/show:

```bash
adclip brand list
adclip brand show morrow
```

`show` returns a full brand snapshot including products, sources, and claims.

## Add a product

```bash
adclip brand add-product morrow \
  --name "Daily Barrier Moisturizer" \
  --value-prop "Lightweight daily moisture for dry or sensitive skin" \
  --audiences "Adults with dry skin,Adults with sensitive skin" \
  --offers "20% off first order"
```

The returned `prd_...` ID can be used to attach sources and claims to that exact product.

## Add sources

External/reference URL:

```bash
adclip brand add-source morrow \
  --title "Product page" \
  --kind product_page \
  --rights owned \
  --uri https://example.com/moisturizer
```

Local file:

```bash
adclip brand add-source morrow \
  --title "Approved product notes" \
  --kind reference \
  --rights owned \
  --file ./product-notes.pdf
```

Local files are copied into the global SHA-256 artifact store. The source record points to:

```text
artifact://sha256/<digest>
```

rather than to the original filesystem path. The original filename/media type may be retained as metadata, but portable provenance does not include the user's absolute local path by default.

### Rights status

Current rights values:

```text
unknown
owned
licensed
public_domain
permission_granted
reference_only
```

Rights are explicit metadata, not a legal determination made automatically by adclip.

## Add claims and evidence

Claims start `unreviewed` unless explicitly assigned another status.

```bash
adclip brand add-claim morrow \
  --text "Fragrance free" \
  --status approved \
  --product-id prd_... \
  --evidence src_...
```

Current statuses:

```text
unreviewed
approved
restricted
rejected
```

Evidence source IDs must belong to the same brand. This prevents accidental cross-brand substantiation.

## Current boundary

S2A establishes **persistent structured brand/source state**. It does not yet automatically:

- crawl a website;
- extract brand voice or products;
- parse documents into normalized source text;
- propose claims from sources;
- promote claims to approved without review;
- inject BrandKit context into current `AdBrief` generation;
- cite source/claim IDs in generated creative provenance.

Those are S2B/S2C work in [`ROADMAP.md`](ROADMAP.md).

The next important transition is:

```text
persistent BrandKit / SourceLibrary
  -> ingestion + editable extraction
  -> approved claims / selected sources
  -> CampaignBriefV2 references persistent IDs
  -> generated creative records source/claim lineage
```

That keeps source truth separate from generated marketing language and allows campaign bundles to carry a minimal portable snapshot of the exact brand context they depended on.
