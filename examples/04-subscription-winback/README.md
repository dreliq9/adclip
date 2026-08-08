# Subscription win-back

**Business goal:** reactivate lapsed subscribers.  
**Audience:** coffee subscribers with no shipment in 45+ days.  
**Channel:** email.  
**Offer:** free shipping on the next box.  
**Primary lifecycle question:** can a value reminder plus a modest incentive recover inactive customers without resorting to fake urgency?

This example focuses on owned-channel lifecycle marketing rather than acquisition creative.

The checked-in sequence is:

```text
1. email_01_reminder.json   reminder / product rediscovery
2. email_02_value.json      value reinforcement
3. email_03_offer.json      incentive
```

Render any message locally with the same campaign brief. For example:

```bash
adclip email render \
  examples/04-subscription-winback/email_brief.json \
  examples/04-subscription-winback/email_03_offer.json \
  --output-dir ./adclip_winback_email_render
```

`email_brief.json` is also ready for sequence generation when a compatible text provider is configured.

A marketer could later compare free shipping versus a percentage discount as separate campaign hypotheses while keeping the rest of the sequence controlled.
