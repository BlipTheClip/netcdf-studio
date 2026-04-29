## Summary

<!-- One or two sentences describing what this PR does and why. -->

Closes #<!-- issue number -->

## Type of change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that causes existing functionality to change)
- [ ] Refactor (no functional change)
- [ ] Documentation update
- [ ] Dependency update

## Module(s) affected

- [ ] A — Downloader
- [ ] B — Processor
- [ ] C — Map imagery
- [ ] D — Visual workbench
- [ ] E — MCP interface
- [ ] Backend infrastructure (main.py, environment.yml, etc.)
- [ ] Frontend infrastructure
- [ ] Documentation / GitHub templates

## Changes made

<!-- Bullet list of the specific changes. Be concrete: function names, file paths, endpoint names. -->

-
-
-

## Scientific correctness

<!-- This section is required for any PR that touches computation in backend/core/. -->

**Does this PR introduce or modify a scientific computation?**
- [ ] No — skip the rest of this section
- [ ] Yes — fill in below

**What computation was changed or added?**

<!-- Describe the formula, algorithm, or processing step. -->

**How was correctness verified?**

<!-- Examples:
- Compared Niño 3.4 output against NOAA/CPC monthly values for 2000–2020
- Verified area-weighted global mean temperature matches published GISTEMP values
- Confirmed CDD values match xclim output on the same input file
-->

**Are the following invariants preserved?**

- [ ] Spatial averages use cosine-latitude weighting
- [ ] Base period is configurable (not hardcoded)
- [ ] Pressure level selection occurs before data is loaded into memory
- [ ] Conservative regridding is used for precipitation and fluxes
- [ ] Non-standard calendars (360-day, noleap) are handled correctly

## Testing

- [ ] Existing tests pass (`pytest backend/tests/ -v`)
- [ ] New tests added for new core functions
- [ ] Tested with a real `.nc` file (not only with mock data)
- [ ] Tested with a non-standard calendar file (if calendar handling was touched)

**Test file / data used:**

<!-- e.g. "CMIP6 CESM2 tas monthly file from ESGF, noleap calendar, 1x1° grid" -->

## Frontend changes

- [ ] No frontend changes
- [ ] Tested in Electron dev mode (`npm run electron:dev`)
- [ ] New API response shape added to `src/api/types.ts`
- [ ] Tested in both light/dark mode (if UI was changed)

## Checklist

- [ ] Code follows the conventions in `CONTRIBUTING.md`
- [ ] `black backend/` passes with no changes
- [ ] `ruff check backend/` passes with no warnings
- [ ] `mypy backend/` passes with no new errors
- [ ] No `print()` statements — logging only
- [ ] No hardcoded file paths, credentials, or base periods
- [ ] `CLAUDE.md` updated if architecture decisions changed
