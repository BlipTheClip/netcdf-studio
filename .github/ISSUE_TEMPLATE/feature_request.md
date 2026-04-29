---
name: Feature request
about: Suggest a new feature or improvement for NetCDF Studio
title: "[FEAT] "
labels: enhancement
assignees: ""
---

## Problem this feature solves

A clear description of the problem or limitation you are facing. What workflow does this block or make unnecessarily difficult?

> Example: "When working with CESM Large Ensemble (40 members), I have to process each member separately because there is no way to batch-compute Niño 3.4 across files."

## Proposed solution

Describe the solution you would like. Be as specific as possible:

- Which module would this belong to? (A: downloader / B: processor / C: imagery / D: visualiser / E: MCP)
- What would the user interaction look like?
- What would the API endpoint or function signature look like?

## Scientific motivation

If this is a new climate index, diagnostic, or processing method, please provide:

- **Reference paper or standard:** e.g. "ETCCDI index Rx5day as defined in Zhang et al. (2011)"
- **Formula or algorithm:** brief description or equation
- **Typical input:** variable, frequency, grid
- **Expected output:** what the result should look like

This helps reviewers verify that the implementation is scientifically correct.

## Alternatives considered

Are there existing workarounds or alternative approaches you have tried? Why are they insufficient?

## Implementation notes (optional)

If you have thoughts on how this could be implemented, or know of a relevant Python library, please share:

- Relevant libraries: e.g. `climpact`, `xclim`, `eofs`
- Known edge cases or tricky aspects (e.g. calendar handling, masked oceans, wrap-around longitudes)
- Approximate scope: small (< 1 day), medium (1–3 days), large (> 3 days)

## Would you be willing to implement this?

- [ ] Yes, I can open a PR
- [ ] Yes, but I would need guidance
- [ ] No, I am just requesting it
