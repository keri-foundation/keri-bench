# Security Policy

## Reporting a vulnerability

**Please do not open a public issue, pull request, or discussion for a security problem.**

Two private channels, either is fine:

- **GitHub private vulnerability reporting** — the *Report a vulnerability* button under this repository's **Security** tab. This is the one we prefer: it keeps the report, the discussion and the fix in one place, and it lets us credit you when an advisory is published.
- **Email `security@bakobo.com`** — if you would rather not use GitHub, or the problem spans more than one of our repositories.

## What to include

Enough for us to reproduce it. In practice that means what you did, what happened, and what you expected instead — plus the version or commit you were on, and your sense of what an attacker gains. A proof of concept helps and is not required; a clear description of the mechanism is worth more than a script we cannot run.

If you are unsure whether what you found is a vulnerability, report it anyway. We would rather read a false alarm than miss a real one, and we will not treat a good-faith mistake as noise.

## What happens next

We will acknowledge your report within **three business days**, and tell you within **ten** whether we consider it a vulnerability and what we intend to do. If a fix is going to take longer than that, you will hear the reason rather than silence.

When a fix ships we publish a GitHub security advisory naming the issue, the affected versions and the fix. We will credit you by whatever name and link you want, or leave you out of it entirely — your call, and we will ask before publishing rather than assume.

Bakobo is a small company. These are commitments about *responsiveness*, not a guarantee that every report is fixed quickly; some are hard, and some we will decline with our reasoning written down.

## Scope

keri-bench is a measurement harness that an operator runs on a machine they control, against a stack they deploy for the purpose. It is not a service, and it holds no credentials of anyone else's. What is ours:

- the harness itself, `src/keri_bench/`: its driver, fault proxy, process control, timeline and report code, and the synthetic stack it calibrates against;
- the documentation site's build, `tools/site_source.py` and `scripts/site-source`, which publishes committed results to <https://keri-foundation.github.io/keri-bench/>;
- this repository's GitHub Actions workflows.

Examples of what we want to hear about: a scenario, timeline or provenance file that makes the harness run code or write outside its output directory; a committed result that makes the site publish active content; a workflow that exposes a token or runs untrusted code with write permissions.

What is not ours: the stacks keri-bench measures. A vulnerability in one of them belongs to that project, even when keri-bench is how you noticed it: keripy's to [WebOfTrust/keripy](https://github.com/WebOfTrust/keripy), the Registrar's to [bakobo/witness](https://github.com/bakobo/witness), and imbu's or heti's, which are not public, to `security@bakobo.com`. A slow, failing or lost credential in a published result is a measurement, not a vulnerability in the harness.

A vulnerability in a dependency should go to that project, not to us. If you are not sure which side of the line something falls on, report it here and we will route it — that is our job, not yours.

## Coordinated disclosure

Report privately, give us a chance to ship a fix, and we will work to a timeline with you. Our default is that a fix and an advisory go out together, and that the advisory is public within 90 days of your report whether or not the fix is complete — a deadline we hold ourselves to, so that reporting to us is never a way for a problem to disappear.

If a vulnerability is being actively exploited, tell us that up front and we will treat the timeline as irrelevant.

## Safe harbour

We will not pursue or support legal action against anyone who reports a vulnerability in good faith through the channels above, and who does not access, modify or destroy data belonging to anyone else, degrade a service other people are relying on, or use the finding for anything except the report. Testing against your own deployment is always fine.

There is no bug bounty. We are not able to pay for reports, and we would rather say so plainly than imply otherwise.

## Known accepted risks

- The fault proxy, the synthetic stack's processes and the harness's own listeners bind to `127.0.0.1` with no authentication. The harness assumes a single host its operator controls, with no other untrusted users on it; that is a design choice for a measurement instrument, recorded in `this.i`, not an oversight.
- Scenarios are trusted input. A scenario names adapters, commands and stack versions to run, so running someone else's scenario is running their code.

## This repository's licence carries no warranty

Everything here ships under `LICENSE`, which disclaims warranties. Nothing in this policy changes that — it describes how we intend to behave, not a contractual obligation.
