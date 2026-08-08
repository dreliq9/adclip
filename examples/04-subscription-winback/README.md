# Subscription win-back

**Business goal:** reactivate lapsed subscribers.  
**Audience:** coffee subscribers with no shipment in 45+ days.  
**Channel:** email.  
**Offer:** free shipping on the next box.  
**Primary lifecycle question:** can a value reminder plus a modest incentive recover inactive customers without resorting to fake urgency?

This example focuses on owned-channel lifecycle marketing rather than acquisition creative.

Generate the sequence locally:

```bash
adclip email generate \
  examples/04-subscription-winback/email_brief.json \
  --provider fake
```

The intended sequence is:

```text
1. reminder / product rediscovery
2. value reinforcement
3. incentive
```

A marketer could later compare free shipping versus a percentage discount as separate campaign hypotheses while keeping the rest of the sequence controlled.
