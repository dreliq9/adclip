"""Email campaign authoring, editing, validation, and export."""

from adclip.email.delivery import (
    EmailDeliveryProvider,
    EmailDeliveryRequest,
    EmailDeliveryResult,
)
from adclip.email.edit import apply_email_patch
from adclip.email.generate import generate_email_documents, scaffold_email_documents
from adclip.email.package import (
    edit_email_campaign_variant,
    load_email_document,
    write_email_campaign_package,
)
from adclip.email.render import (
    build_email_headers,
    build_email_message,
    render_email_html,
    render_email_text,
)
from adclip.email.schema import (
    EmailBlock,
    EmailCampaignBrief,
    EmailCampaignDocument,
    EmailCampaignPatch,
    EmailContent,
    EmailDeliveryPlan,
    EmailSender,
    EmailTheme,
    EmailTracking,
    EmailValidationReport,
)
from adclip.email.validate import validate_email_document, validate_email_html

__all__ = [
    "EmailBlock",
    "EmailCampaignBrief",
    "EmailCampaignDocument",
    "EmailCampaignPatch",
    "EmailContent",
    "EmailDeliveryPlan",
    "EmailDeliveryProvider",
    "EmailDeliveryRequest",
    "EmailDeliveryResult",
    "EmailSender",
    "EmailTheme",
    "EmailTracking",
    "EmailValidationReport",
    "apply_email_patch",
    "build_email_headers",
    "build_email_message",
    "edit_email_campaign_variant",
    "generate_email_documents",
    "load_email_document",
    "render_email_html",
    "render_email_text",
    "scaffold_email_documents",
    "validate_email_document",
    "validate_email_html",
    "write_email_campaign_package",
]
