# cli-hmi quick start

This folder is a temporary external wrapper for demo use.
It does not participate in the original project flow.

## Mapping run

Use prebuilt aggregated rules:

```bash
python cli-hmi/run.py --aggregated-rule-set <real_aggregated_rule_set.json> --database <real_database.json> [--decisions <decisions.json>] [--out result.json]
```

Use one kmm_rule file (MVP):

```bash
python cli-hmi/run.py --kmm-rule description/kmm_rule_RWR-khn_CT-castears-z2414_Replace.json.example --database <real_database.json> [--decisions <decisions.json>] [--out result.json]
```

Interactive mode:

```bash
python cli-hmi/run.py --interactive
```

## Visualization

Interactive visualization wrapper:

```bash
python cli-hmi/visualize_interactive.py
```

Core CLI visualize (M1 details on by default):

```bash
python -m modmanager.cli visualize --forest <result.json> --format ascii
```

Disable M1 details explicitly:

```bash
python -m modmanager.cli visualize --forest <result.json> --format ascii --no-show-m1-details
```

## Test runner

Interactive test menu with report export:

```bash
python cli-hmi/test_runner.py
```

Reports are written to:
- cli-hmi/reports/

## Expected output

- Mapping JSON keys: warnings, errors, forest, final_mapping, summary
- Test summary: total, pass, fail, error, skipped, duration
- Test report export: JSON + Markdown
- Exit code: 0 when errors is empty, otherwise 2

## Smoke test

```bash
python cli-hmi/smoke_test.py --aggregated-rule-set <real_aggregated_rule_set.json> --database <real_database.json>
```

Or use env vars:

```bash
HMI_AGGREGATED_RULE_SET=<real_aggregated_rule_set.json> HMI_DATABASE=<real_database.json> python cli-hmi/smoke_test.py
```

## Documents

- Demo guide: cli-hmi/DEMO_GUIDE.md
- Implementation summary: repo_memory/DEMO_M1_IMPLEMENTATION_SUMMARY.md
