"""Transport-neutral performance ingestion and creative-learning services."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from adclip.connectors.meta_performance import (
    MetaPerformanceClient,
    normalize_meta_insight,
)
from adclip.performance.analysis import (
    available_windows,
    compare_observations,
    select_window,
    summarize_observations,
)
from adclip.performance.identity import deployment_id_for
from adclip.performance.schema import DeploymentRecord, utc_now
from adclip.performance.store import (
    campaign_manifest,
    find_creative_entry,
    load_deployments,
    load_observations,
    upsert_deployment,
    upsert_observations,
    write_deployments,
)
from adclip.runtime import RuntimePolicy


def _date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Expected YYYY-MM-DD date, got {value!r}") from exc


def _meta_account(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Meta account_id must not be empty")
    return cleaned if cleaned.startswith("act_") else f"act_{cleaned}"


def _same_meta_account(left: str, right: str) -> bool:
    return left.removeprefix("act_") == right.removeprefix("act_")


class PerformanceApplication:
    """Portable deployment lineage plus read-only performance synchronization."""

    def __init__(self, *, runtime_policy: RuntimePolicy | None = None) -> None:
        self.runtime_policy = runtime_policy or RuntimePolicy.from_env()

    def link_meta(
        self,
        campaign_dir: str,
        *,
        variant_id: str,
        account_id: str,
        ad_id: str,
        external_campaign_id: str | None = None,
        external_adset_id: str | None = None,
        external_creative_id: str | None = None,
        name: str | None = None,
    ) -> dict[str, object]:
        root = Path(campaign_dir)
        if not root.is_dir():
            return {"ok": False, "error": f"Campaign dir not found: {campaign_dir}"}
        try:
            manifest = campaign_manifest(root)
            entry = find_creative_entry(root, variant_id=variant_id)
            account = _meta_account(account_id)
            deployment_id = deployment_id_for("meta", account, str(ad_id))
            existing = {item.id: item for item in load_deployments(root)}
            prior = existing.get(deployment_id)
            if prior is not None and prior.creative_id != str(entry["creative_id"]):
                raise ValueError(
                    f"Meta ad {ad_id} in {account} is already linked to creative "
                    f"{prior.creative_id} (variant {prior.variant_id}); refusing to "
                    "silently replace deployment lineage"
                )
            metadata = {
                "artifact_path": entry.get("path"),
                "artifact_sha256": entry.get("artifact_sha256"),
            }
            deployment = DeploymentRecord(
                id=deployment_id,
                campaign_id=str(manifest["campaign_id"]),
                creative_id=str(entry["creative_id"]),
                variant_id=variant_id,
                format=(str(entry["format"]) if entry.get("format") else None),
                platform="meta",
                account_id=account,
                external_ad_id=str(ad_id),
                external_campaign_id=(
                    str(external_campaign_id) if external_campaign_id else None
                ),
                external_adset_id=(
                    str(external_adset_id) if external_adset_id else None
                ),
                external_creative_id=(
                    str(external_creative_id) if external_creative_id else None
                ),
                external_name=name,
                linked_at=(prior.linked_at if prior is not None else utc_now()),
                last_synced_at=(prior.last_synced_at if prior is not None else None),
                status=(prior.status if prior is not None else None),
                metadata={key: value for key, value in metadata.items() if value is not None},
            )
            upsert_deployment(root, deployment)
        except (FileNotFoundError, KeyError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "deployment": deployment.model_dump(mode="json")}

    def deployments(self, campaign_dir: str) -> dict[str, object]:
        try:
            items = load_deployments(campaign_dir)
        except (FileNotFoundError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "deployments": [item.model_dump(mode="json") for item in items],
        }

    def sync_meta(
        self,
        campaign_dir: str,
        *,
        since: str | date,
        until: str | date,
        account_id: str | None = None,
        action_report_time: str = "conversion",
    ) -> dict[str, object]:
        try:
            start = _date(since)
            end = _date(until)
            if end < start:
                raise ValueError("until must be on or after since")
            deployments = load_deployments(campaign_dir)
        except (FileNotFoundError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

        selected = [item for item in deployments if item.platform == "meta"]
        if account_id:
            account = _meta_account(account_id)
            selected = [
                item
                for item in selected
                if _same_meta_account(item.account_id, account)
            ]
        if not selected:
            return {
                "ok": False,
                "error": "No linked Meta deployments match this sync request",
            }

        try:
            client = MetaPerformanceClient.from_env(self.runtime_policy)
        except (RuntimeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

        observations = []
        errors: list[dict[str, str]] = []
        updated_by_id = {item.id: item for item in deployments}
        for deployment in selected:
            try:
                ad = client.get_ad(deployment.external_ad_id)
                returned_ad_id = ad.get("id")
                if returned_ad_id is not None and str(returned_ad_id) != deployment.external_ad_id:
                    raise ValueError(
                        f"Meta returned ad id {returned_ad_id!r} for linked ad "
                        f"{deployment.external_ad_id!r}; refusing to accept observations"
                    )
                ad_account = ad.get("account_id")
                if isinstance(ad_account, str) and not _same_meta_account(
                    deployment.account_id,
                    ad_account,
                ):
                    raise ValueError(
                        f"Linked ad {deployment.external_ad_id} belongs to account "
                        f"{ad_account}, not {deployment.account_id}"
                    )
                creative = ad.get("creative", {})
                if not isinstance(creative, dict):
                    creative = {}
                updated = deployment.model_copy(
                    update={
                        "external_campaign_id": (
                            str(ad.get("campaign_id"))
                            if ad.get("campaign_id")
                            else deployment.external_campaign_id
                        ),
                        "external_adset_id": (
                            str(ad.get("adset_id"))
                            if ad.get("adset_id")
                            else deployment.external_adset_id
                        ),
                        "external_creative_id": (
                            str(creative.get("id"))
                            if creative.get("id")
                            else deployment.external_creative_id
                        ),
                        "external_name": (
                            str(ad.get("name"))
                            if ad.get("name")
                            else deployment.external_name
                        ),
                        "status": (
                            str(ad.get("effective_status"))
                            if ad.get("effective_status")
                            else deployment.status
                        ),
                        "last_synced_at": utc_now(),
                    }
                )
                rows = client.get_ad_insights(
                    deployment.external_ad_id,
                    since=start,
                    until=end,
                    action_report_time=action_report_time,
                )
                fetched_at = utc_now()
                observations.extend(
                    normalize_meta_insight(
                        row,
                        updated,
                        requested_start=start,
                        requested_end=end,
                        api_version=client.api_version,
                        action_report_time=action_report_time,
                        fetched_at=fetched_at,
                    )
                    for row in rows
                )
                updated_by_id[updated.id] = updated
            except (RuntimeError, ValueError) as exc:
                errors.append(
                    {
                        "deployment_id": deployment.id,
                        "ad_id": deployment.external_ad_id,
                        "error": str(exc),
                    }
                )

        write_deployments(campaign_dir, list(updated_by_id.values()))
        if observations:
            upsert_observations(campaign_dir, observations)

        summary = summarize_observations(observations)
        return {
            "ok": not errors,
            "partial": bool(errors) and bool(observations),
            "read_only": True,
            "platform": "meta",
            "api_version": client.api_version,
            "window": {
                "since": start.isoformat(),
                "until": end.isoformat(),
                "action_report_time": action_report_time,
            },
            "deployment_count": len(selected),
            "observation_count": len(observations),
            "errors": errors,
            "summary": summary,
        }

    def report(
        self,
        campaign_dir: str,
        *,
        since: str | date | None = None,
        until: str | date | None = None,
        action_report_time: str | None = None,
    ) -> dict[str, object]:
        try:
            observations = load_observations(campaign_dir)
            start = _date(since) if since is not None else None
            end = _date(until) if until is not None else None
            selected, window = select_window(
                observations,
                since=start,
                until=end,
                action_report_time=action_report_time,
            )
        except (FileNotFoundError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

        return {
            "ok": True,
            "descriptive_only": True,
            "selected_window": (
                {
                    "since": window[0].isoformat(),
                    "until": window[1].isoformat(),
                    "action_report_time": window[2],
                }
                if window
                else None
            ),
            "available_windows": [
                {
                    "since": item[0].isoformat(),
                    "until": item[1].isoformat(),
                    "action_report_time": item[2],
                }
                for item in available_windows(observations)
            ],
            "observation_count": len(selected),
            "summary": summarize_observations(selected),
        }

    def compare(
        self,
        campaign_dir: str,
        *,
        since: str | date,
        until: str | date,
        metric: str = "ctr",
        action_type: str | None = None,
        action_report_time: str | None = None,
    ) -> dict[str, object]:
        try:
            start = _date(since)
            end = _date(until)
            observations = load_observations(campaign_dir)
            selected, window = select_window(
                observations,
                since=start,
                until=end,
                action_report_time=action_report_time,
            )
            comparison = compare_observations(
                selected,
                metric=metric,
                action_type=action_type,
            )
        except (FileNotFoundError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "window": {
                "since": start.isoformat(),
                "until": end.isoformat(),
                "action_report_time": window[2] if window else action_report_time,
            },
            **comparison,
        }
