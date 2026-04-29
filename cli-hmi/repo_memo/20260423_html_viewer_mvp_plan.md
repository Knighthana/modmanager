# Filemappingforest Browser Viewer MVP Notes

Date: 2026-04-23

## Confirmed Scope
- Static browser display first.
- Input source is offline JSON file.
- Output is a standalone HTML wrapper page.
- Three tabs: forest, warnings/errors, final_mapping.
- Forest interaction: zoom and pan only.
- Target scale: about 200 nodes; prioritize functional availability.
- Do not add a new CLI subcommand.
- Keep using existing visualize entry and extend format options.
- Output placement convention remains in cli-hmi directory.
- Overwrite only when the full filename matches.
- MVP principle: show first, then iterate.

## Implementation Decisions
- Extend visualize format to include html.
- Keep ASCII/DOT/SVG behavior unchanged.
- Build standalone HTML with inline CSS and JS, no external frontend dependency.
- Forest graph uses SVG rendering in browser with client-side pan/zoom.
- Warnings/errors and final_mapping are rendered in separate tabs.

## Test Focus
- HTML output contains required tabs and sections.
- CLI visualize --format html works and returns code 0.
- Existing visualization paths (ascii/dot/svg) remain backward compatible.

## Environment Notes
- No new Node/frontend package is required for this MVP implementation.
- Therefore no nvm-based package installation is needed at this stage.
