"""Structured editing operations for canonical email campaign documents."""

from __future__ import annotations

from typing import Any

from adclip.email.schema import (
    EmailCampaignDocument,
    EmailCampaignPatch,
    EmailSender,
    EmailTheme,
    EmailTracking,
)


def _merge_model(model, changes: dict[str, Any], model_type):
    if not changes:
        return model
    payload = {**model.model_dump(), **changes}
    return model_type.model_validate(payload)


def apply_email_patch(
    document: EmailCampaignDocument,
    patch: EmailCampaignPatch,
) -> EmailCampaignDocument:
    """Apply a validated patch without exposing arbitrary object paths."""

    payload = document.model_dump()
    if patch.subject is not None:
        payload["subject"] = patch.subject
    if patch.preview_text is not None:
        payload["preview_text"] = patch.preview_text

    payload["sender"] = _merge_model(document.sender, patch.sender, EmailSender).model_dump()
    payload["theme"] = _merge_model(document.theme, patch.theme, EmailTheme).model_dump()
    payload["tracking"] = _merge_model(
        document.tracking, patch.tracking, EmailTracking
    ).model_dump()

    blocks = [block.model_copy(deep=True) for block in document.blocks]
    by_id = {block.id: block for block in blocks}

    missing_updates = sorted(set(patch.block_updates) - set(by_id))
    if missing_updates:
        raise ValueError(f"Cannot update unknown block ids: {missing_updates}")

    for block_id, changes in patch.block_updates.items():
        if "id" in changes and changes["id"] != block_id:
            raise ValueError("Block ids are stable and cannot be changed by update")
        current = by_id[block_id]
        updated = current.__class__.model_validate(
            {**current.model_dump(), **changes, "id": block_id}
        )
        index = next(i for i, block in enumerate(blocks) if block.id == block_id)
        blocks[index] = updated
        by_id[block_id] = updated

    delete_ids = set(patch.delete_blocks)
    unknown_deletes = sorted(delete_ids - set(by_id))
    if unknown_deletes:
        raise ValueError(f"Cannot delete unknown block ids: {unknown_deletes}")
    blocks = [block for block in blocks if block.id not in delete_ids]
    by_id = {block.id: block for block in blocks}

    for insertion in patch.insert_blocks:
        if insertion.block.id in by_id:
            raise ValueError(f"Block id already exists: {insertion.block.id}")
        if insertion.after_id is None:
            blocks.append(insertion.block)
        else:
            if insertion.after_id not in by_id:
                raise ValueError(
                    f"Cannot insert after unknown block id: {insertion.after_id}"
                )
            index = next(
                i for i, block in enumerate(blocks) if block.id == insertion.after_id
            )
            blocks.insert(index + 1, insertion.block)
        by_id[insertion.block.id] = insertion.block

    if patch.order is not None:
        current_ids = [block.id for block in blocks]
        if len(set(patch.order)) != len(patch.order):
            raise ValueError("Patch order contains duplicate block ids")
        if set(patch.order) != set(current_ids):
            missing = sorted(set(current_ids) - set(patch.order))
            unknown = sorted(set(patch.order) - set(current_ids))
            raise ValueError(
                f"Patch order must name every remaining block exactly once; "
                f"missing={missing}, unknown={unknown}"
            )
        blocks = [by_id[block_id] for block_id in patch.order]

    if not blocks:
        raise ValueError("Email campaign must contain at least one content block")
    payload["blocks"] = [block.model_dump() for block in blocks]
    return EmailCampaignDocument.model_validate(payload)
