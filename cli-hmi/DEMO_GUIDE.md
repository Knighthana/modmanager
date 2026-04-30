# Demo Guide (cli-hmi)

## Environment
- Python >= 3.10
- Optional: graphviz (required only for SVG output)
- Run from repository root

## Default Demo Inputs
- KMM rule:
- description/kmm_rule_RWR-khn_CT-castears-z2414_Replace.json.example
- Database:
- description/database.json.example

## Fast Path (3-5 minutes)
1. Run mapping from single rule:
```bash
python cli-hmi/run.py --kmm-rule description/kmm_rule_RWR-khn_CT-castears-z2414_Replace.json.example --database description/database.json.example --out cli-hmi/reports/demo_result.json
```
2. Run visualization (detail mode enabled by default):
```bash
python -m modmanager.cli visualize --forest cli-hmi/reports/demo_result.json --format ascii
```
3. Run full tests with report export:
```bash
python cli-hmi/test_runner.py
```
- In menu: choose Run ALL, then export JSON/Markdown.

## Full Path (10-15 minutes)
1. Mapping run with interactive prompts:
```bash
python cli-hmi/run.py --interactive
```
2. Visualize ASCII and DOT outputs:
```bash
python cli-hmi/visualize_interactive.py
```
3. Execute repository tests by module and full run:
```bash
python cli-hmi/test_runner.py
```
4. Confirm reports under:
- cli-hmi/reports/

## How to Read Outputs
- Terminal summary:
- Total, Passed, Failed, Errors, Duration
- Pass details and fail details with rerun commands
- JSON report:
- Machine-readable run stats and failed test metadata
- Markdown report:
- Management-friendly summary table and failure section
- Visualization detail fields:
- action_order: conflict resolution precedence
- provenance_ref: origin reference for an action
- sidecar_ref: sidecar provenance pointer

## Troubleshooting
- graphviz not found:
- Use ascii or dot format instead of svg.
- import/module error:
- Run from repo root and ensure venv is activated.
- aggregator validation error:
- Input rule is invalid under current constraints; fix rule fields or run with prebuilt aggregated_rule_set.
- test failures:
- Use rerun command shown in report for targeted debugging.

## Evidence Package for Presentation
- Keep these files from a successful run:
- cli-hmi/reports/*.json
- cli-hmi/reports/*.md
- optional visualization outputs (.dot/.svg)
- one terminal transcript screenshot with summary section
