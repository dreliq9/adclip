from adclip.email.lint import lint_rendered_message
from adclip.email.render import (
    build_email_headers,
    render_email_html,
    render_email_text,
)
from adclip.email.schema import EmailBlock, EmailCampaignBrief, EmailMessage


def _brief():
    return EmailCampaignBrief(
        name="Launch",
        product="Widget",
        value_prop="Save setup time",
        audience="Small teams",
        objective="Drive trials",
        sender_name="Acme",
        sender_email="hello@example.com",
        brand_colors=["#111827", "#2563EB"],
    )


def _message():
    return EmailMessage(
        id="email_01",
        name="Launch",
        subject="Build faster",
        preheader="A simpler way to test the idea.",
        blocks=[
            EmailBlock(id="headline", kind="heading", text="Build faster"),
            EmailBlock(
                id="body",
                kind="paragraph",
                text="Test the idea before scaling the spend.",
            ),
            EmailBlock(
                id="cta",
                kind="button",
                text="Start testing",
                href="https://example.com/start",
            ),
        ],
    )


def test_rendered_marketing_email_is_editable_and_compliant():
    brief = _brief()
    message = _message()
    html = render_email_html(brief, message)
    text = render_email_text(brief, message)
    headers = build_email_headers(brief, message)

    assert "<!-- adclip:block:headline:start -->" in html
    assert 'role="presentation"' in html
    assert "{{unsubscribe_url}}" in html
    assert "List-Unsubscribe" in headers
    assert "Start testing: https://example.com/start" in text

    report = lint_rendered_message(
        brief,
        message,
        html_source=html,
        plain_text=text,
        headers=headers,
    )
    assert report["ok"] is True
    assert report["summary"]["errors"] == 0


def test_linter_catches_unsafe_html_and_missing_image_alt():
    brief = _brief()
    message = _message()
    html = (
        '<html lang="en"><body><table role="presentation">'
        '<tr><td><img src="http://example.com/x.png"><script>x()</script>'
        "</td></tr></table></body></html>"
    )
    report = lint_rendered_message(
        brief,
        message,
        html_source=html,
        plain_text="fallback",
        headers=build_email_headers(brief, message),
    )
    codes = {issue["code"] for issue in report["issues"]}
    assert report["ok"] is False
    assert "unsafe_tag" in codes
    assert "image_missing_alt" in codes
