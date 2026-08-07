import pytest

from adclip.runtime import ProviderRequirements, RuntimeMode, RuntimePolicy


def test_runtime_mode_coerce():
    assert RuntimeMode.coerce("offline") is RuntimeMode.OFFLINE
    assert RuntimePolicy(mode="offline").mode is RuntimeMode.OFFLINE
    with pytest.raises(ValueError, match="Unknown ADCLIP_RUNTIME_MODE"):
        RuntimeMode.coerce("nope")


def test_offline_blocks_network_provider():
    policy = RuntimePolicy(mode=RuntimeMode.OFFLINE)
    with pytest.raises(RuntimeError, match="requires network access"):
        policy.check_provider("remote", ProviderRequirements(network=True))


def test_restricted_network_uses_allowlist():
    policy = RuntimePolicy(
        mode=RuntimeMode.RESTRICTED_NETWORK,
        allowed_network_providers=frozenset({"approved"}),
    )
    policy.check_provider("approved", ProviderRequirements(network=True))
    with pytest.raises(RuntimeError, match="not in the restricted-network allowlist"):
        policy.check_provider("blocked", ProviderRequirements(network=True))


def test_paid_provider_requires_explicit_authorization():
    policy = RuntimePolicy(mode=RuntimeMode.ONLINE, allow_paid_apis=False)
    with pytest.raises(RuntimeError, match="paid API charges"):
        policy.check_provider("paid", ProviderRequirements(paid_api=True))


def test_air_gapped_always_blocks_host_session():
    policy = RuntimePolicy(
        mode=RuntimeMode.AIR_GAPPED,
        allow_host_sessions=True,
    )
    with pytest.raises(RuntimeError, match="requires a host session"):
        policy.check_provider(
            "sampling",
            ProviderRequirements(host_session=True),
        )


def test_runtime_policy_from_env(monkeypatch):
    monkeypatch.setenv("ADCLIP_RUNTIME_MODE", "restricted_network")
    monkeypatch.setenv("ADCLIP_ALLOWED_NETWORK_PROVIDERS", "one, two")
    monkeypatch.setenv("ADCLIP_ALLOW_LIVE_APIS", "1")
    policy = RuntimePolicy.from_env()
    assert policy.mode is RuntimeMode.RESTRICTED_NETWORK
    assert policy.allowed_network_providers == frozenset({"one", "two"})
    assert policy.allow_paid_apis is True
