---
name: Bug report
about: Report incorrect behaviour, a crash, or a scientific error
title: "[BUG] "
labels: bug
assignees: ""
---

## Description

A clear and concise description of what the bug is.

## Steps to reproduce

1. Open file `...`
2. Set variable to `...`
3. Click `...`
4. See error

## Expected behaviour

What you expected to happen.

## Actual behaviour

What actually happened. Paste any error message or traceback in a code block:

```
paste error here
```

## Environment

| Field | Value |
|---|---|
| OS | e.g. Windows 11, macOS 14, Ubuntu 22.04 |
| NetCDF Studio version | e.g. 0.1.0 |
| Python version | `python --version` |
| xarray version | `python -c "import xarray; print(xarray.__version__)"` |
| Installation method | conda / pip |

## Data details

If the bug is related to a specific file or data source, please provide:

- **Data source:** e.g. CMIP6 / ERA5 / ESGF / Copernicus CDS
- **Variable:** e.g. `tas`, `pr`, `tos`
- **Frequency:** e.g. monthly, daily
- **Calendar:** e.g. gregorian, 360_day, noleap
- **File size:** approximate
- **Can you share a minimal sample file?** yes / no

## Backend logs

If the backend produced logs, paste the relevant lines here:

```
paste logs here
```

## Additional context

Any other context, screenshots, or information that might help diagnose the issue.

---

> **Scientific error?** If this bug produces scientifically incorrect results (wrong anomaly, unweighted spatial mean, incorrect calendar handling, etc.), please add the label `scientific-error` and describe how you verified the expected result (e.g. comparison against a reference dataset or published value).
