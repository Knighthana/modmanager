# cli-hmi quick start

This folder is a temporary external wrapper for demo use.
It does not participate in the original project flow.

## Run

Parameter mode:

```bash
python cli-hmi/run.py --aggregated-rule-set <real_aggregated_rule_set.json> --database <real_database.json> [--decisions <decisions.json>] [--out result.json]
```

Interactive mode:

```bash
python cli-hmi/run.py --interactive
```

## Required input

- aggregated_rule_set json path
- database json path
- optional decisions json path

## Expected output

- JSON result with keys: warnings, errors, forest, final_mapping
- Summary counts in output (warnings/errors/forest/final_mapping)
- Exit code: 0 when errors is empty, otherwise 2

## Smoke test

```bash
python cli-hmi/smoke_test.py --aggregated-rule-set <real_aggregated_rule_set.json> --database <real_database.json>
```

Or use env vars:

```bash
HMI_AGGREGATED_RULE_SET=<real_aggregated_rule_set.json> HMI_DATABASE=<real_database.json> python cli-hmi/smoke_test.py
```

On success it prints colored [SUCCESS].
