from adclip.policy import check_copy, PolicyReport
from adclip.formats import get_format


def test_default_profile_accepts_clean_copy():
    fmt = get_format("meta_feed_4x5")
    report = check_copy(
        headline="Start Paper Trading Today",
        body="Try our bot risk-free before risking real cash.",
        cta="Start Free",
        format_spec=fmt,
        profile="default",
        must_include=[],
        must_avoid=[],
    )
    assert report.violations == []


def test_char_limit_violation():
    fmt = get_format("google_rsa")  # headline_max = 30
    report = check_copy(
        headline="This Headline Has Way Too Many Characters For Google RSA",
        body="ok",
        cta="c",
        format_spec=fmt,
        profile="default",
        must_include=[],
        must_avoid=[],
    )
    assert any("headline" in v.lower() for v in report.violations)


def test_crypto_profile_blocks_guaranteed_returns():
    fmt = get_format("meta_feed_4x5")
    report = check_copy(
        headline="Guaranteed 10x Returns",
        body="Guaranteed returns every month with our bot",
        cta="Sign up",
        format_spec=fmt,
        profile="crypto",
        must_include=[],
        must_avoid=[],
    )
    assert any("guaranteed" in v.lower() for v in report.violations)


def test_must_include_enforced():
    fmt = get_format("meta_feed_4x5")
    report = check_copy(
        headline="Try our bot",
        body="Our bot is fast",
        cta="Sign up",
        format_spec=fmt,
        profile="default",
        must_include=["free tier"],
        must_avoid=[],
    )
    assert any("free tier" in v.lower() for v in report.violations)


def test_must_avoid_enforced():
    fmt = get_format("meta_feed_4x5")
    report = check_copy(
        headline="Try our bot",
        body="Get rich quick",
        cta="Sign up",
        format_spec=fmt,
        profile="default",
        must_include=[],
        must_avoid=["rich quick"],
    )
    assert any("rich quick" in v.lower() for v in report.violations)


def test_all_caps_body_is_warning_not_violation():
    fmt = get_format("meta_feed_4x5")
    report = check_copy(
        headline="Ok",
        body="BUY NOW DONT MISS OUT",
        cta="c",
        format_spec=fmt,
        profile="default",
        must_include=[],
        must_avoid=[],
    )
    assert report.violations == []
    assert any("caps" in w.lower() for w in report.warnings)
