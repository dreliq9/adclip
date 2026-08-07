"""Portable on-disk package for email campaign variants."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from adclip.email.edit import apply_email_patch
from adclip.email.render import (
    build_email_headers,
    render_email_html,
    render_email_text,
    write_rendered_email,
)
from adclip.email.schema import (
    EmailCampaignBrief,
    EmailCampaignDocument,
    EmailCampaignPatch,
    EmailDeliveryPlan,
)
from adclip.email.validate import summarize_issues, validate_email_document


def _canonical_hash(document: EmailCampaignDocument) -> str:
    payload = json.dumps(
        document.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_email_campaign_package(
    brief: EmailCampaignBrief,
    documents: list[EmailCampaignDocument],
    *,
    delivery_plan: EmailDeliveryPlan | None = None,
) -> dict[str, object]:
    """Write all variants plus a provider-neutral campaign manifest."""

    root = Path(brief.output_dir)
    variants_root = root / "variants"
    variants_root.mkdir(parents=True, exist_ok=True)
    (root / "email_brief.json").write_text(
        json.dumps(brief.model_dump(mode="json"), indent=2), encoding="utf-8"
    )
    if delivery_plan is not None:
        (root / "delivery_plan.json").write_text(
            json.dumps(delivery_plan.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    variants: list[dict[str, object]] = []
    all_valid = True
    for document in documents:
        directory = variants_root / document.variant_id
        directory.mkdir(parents=True, exist_ok=True)
        document_path = directory / "campaign.json"
        document_path.write_text(
            json.dumps(document.model_dump(mode="json"), indent=2), encoding="utf-8"
        )
        artifacts = write_rendered_email(document, directory)
        html_source = Path(artifacts["html"]).read_text(encoding="utf-8")
        text_source = Path(artifacts["text"]).read_text(encoding="utf-8")
        report = validate_email_document(
            document,
            html_source=html_source,
            text_source=text_source,
            headers=build_email_headers(document),
        )
        (directory / "validation.json").write_text(
            json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8"
        )
        all_valid = all_valid and report.ok
        variants.append(
            {
                "variant_id": document.variant_id,
                "subject": document.subject,
                "document": str(document_path.relative_to(root)),
                "html": str(Path(artifacts["html"]).relative_to(root)),
                "text": str(Path(artifacts["text"]).relative_to(root)),
                "eml": str(Path(artifacts["eml"]).relative_to(root)),
                "headers": str(Path(artifacts["headers"]).relative_to(root)),
                "validation": str((directory / "validation.json").relative_to(root)),
                "valid": report.ok,
                "issue_summary": summarize_issues(report.issues),
                "document_sha256": _canonical_hash(document),
            }
        )

    manifest = {
        "schema_version": "email-package/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "campaign_name": brief.campaign_name,
        "message_type": brief.message_type,
        "audience": brief.audience,
        "objective": brief.objective,
        "variant_count": len(documents),
        "valid": all_valid,
        "variants": variants,
        "delivery_authorized": False,
        "sender_readiness": {
            "spf": "external-verification-required",
            "dkim": "external-verification-required",
            "dmarc": "external-verification-required",
            "one_click_unsubscribe_headers": brief.message_type == "marketing",
        },
    }
    manifest_path = root / "email_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {
        "ok": all_valid,
        "campaign_dir": str(root.resolve()),
        "manifest": str(manifest_path.resolve()),
        "variants": variants,
    }


def load_email_document(campaign_dir: str | Path, variant_id: str) -> EmailCampaignDocument:
    path = Path(campaign_dir) / "variants" / variant_id / "campaign.json"
    if not path.exists():
        raise FileNotFoundError(f"Email variant document not found: {path}")
    return EmailCampaignDocument.model_validate_json(path.read_text(encoding="utf-8"))


def edit_email_campaign_variant(
    campaign_dir: str | Path,
    variant_id: str,
    patch: EmailCampaignPatch,
) -> dict[str, object]:
    """Patch one variant and regenerate its delivery artifacts."""

    root = Path(campaign_dir)
    directory = root / "variants" / variant_id
    document = load_email_document(root, variant_id)
    updated = apply_email_patch(document, patch)
    (directory / "campaign.json").write_text(
        json.dumps(updated.model_dump(mode="json"), indent=2), encoding="utf-8"
    )
    artifacts = write_rendered_email(updated, directory)
    html_source = render_email_html(updated)
    text_source = render_email_text(updated)
    report = validate_email_document(
        updated,
        html_source=html_source,
        text_source=text_source,
        headers=build_email_headers(updated),
    )
    validation_path = directory / "validation.json"
    validation_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2), encoding="utf-8"
    )
    return {
        "ok": report.ok,
        "variant_id": variant_id,
        "document_sha256": _canonical_hash(updated),
        "artifacts": artifacts,
        "validation": str(validation_path),
        "issue_summary": summarize_issues(report.issues),
    }
