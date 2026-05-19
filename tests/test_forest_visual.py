from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from modmanager.forest_visual import VisualizationError, visualize_payload


class ForestVisualTests(unittest.TestCase):
    def test_ascii_marks_branching_and_delete(self) -> None:
        payload = {
            "trees": [
                {
                    "root_path": "/dst/a.txt",
                    "warning": "W_FOREST_BRANCHING",
                    "resolved_state": "pending",
                    "refs": [],
                    "changerequest": [
                        {"path": "!", "action": "delete", "mixed_id": "270150:100", "hashtype": "sha256", "hashvalue": "0"},
                        {"path": "/src/a.txt", "action": "replace", "mixed_id": "270150:101", "hashtype": "sha256", "hashvalue": "abc"},
                    ],
                }
            ]
        }

        out = visualize_payload(payload, "ascii")
        self.assertIn("TREES", out)
        self.assertIn("BRANCHING", out)
        self.assertIn("PENDING", out)
        self.assertIn("DELETE(!)", out)

    def test_dot_output_contains_graph_header(self) -> None:
        payload = {
            "trees": [
                {
                    "root_path": "/dst/a.txt",
                    "refs": [],
                    "resolved_state": "",
                    "changerequest": [
                        {"path": "/src/a.txt", "action": "replace", "mixed_id": "270150:100", "hashtype": "sha256", "hashvalue": "abc"}
                    ],
                }
            ]
        }

        out = visualize_payload(payload, "dot")
        self.assertIn("digraph Forest", out)
        self.assertIn("/dst/a.txt", out)

    def test_dot_escapes_special_characters(self) -> None:
        payload = {
            "trees": [
                {
                    "root_path": '/dst/"a\\b\n中.txt',
                    "refs": [],
                    "resolved_state": "",
                    "changerequest": [
                        {
                            "path": '/src/"x\\y\n文.txt',
                            "action": "replace",
                            "mixed_id": "270150:100",
                            "hashtype": "sha256",
                            "hashvalue": "abc",
                        }
                    ],
                }
            ]
        }

        out = visualize_payload(payload, "dot")
        self.assertIn('\\"', out)
        self.assertIn('\\\\', out)
        self.assertIn('\\n', out)

    def test_svg_success_returns_svg_text(self) -> None:
        payload = {
            "trees": [
                {
                    "root_path": "/dst/a.txt",
                    "refs": [],
                    "resolved_state": "",
                    "changerequest": [
                        {
                            "path": "/src/a.txt",
                            "action": "replace",
                            "mixed_id": "270150:100",
                            "hashtype": "sha256",
                            "hashvalue": "abc",
                        }
                    ],
                }
            ]
        }
        completed = subprocess.CompletedProcess(
            args=["dot", "-Tsvg"],
            returncode=0,
            stdout=b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
            stderr=b"",
        )
        with patch("modmanager.forest_visual.subprocess.run", return_value=completed):
            out = visualize_payload(payload, "svg")
        self.assertIn("<svg", out)

    def test_invalid_forest_input_raises_code_2(self) -> None:
        with self.assertRaises(VisualizationError) as ctx:
            visualize_payload({"foo": []}, "ascii")
        self.assertEqual(ctx.exception.code, 2)

    def test_unsupported_format_raises_code_3(self) -> None:
        with self.assertRaises(VisualizationError) as ctx:
            visualize_payload({"trees": []}, "mermaid")
        self.assertEqual(ctx.exception.code, 3)

    def test_svg_missing_dot_raises_code_4(self) -> None:
        payload = {"trees": [{"root_path": "/dst/a.txt", "changerequest": [], "refs": [], "resolved_state": ""}]}
        with patch("modmanager.forest_visual.subprocess.run", side_effect=FileNotFoundError()):
            with self.assertRaises(VisualizationError) as ctx:
                visualize_payload(payload, "svg")
        self.assertEqual(ctx.exception.code, 4)

    def test_unknown_extension_fields_are_non_fatal(self) -> None:
        payload = {
            "trees": [
                {
                    "root_path": "/dst/a.txt",
                    "refs": [],
                    "resolved_state": "",
                    "changerequest": [
                        {
                            "path": "/src/a.txt",
                            "action": "replace",
                            "mixed_id": "270150:100",
                            "hashtype": "sha256",
                            "hashvalue": "abc",
                            "future_meta": {"k": "v"},
                        }
                    ],
                    "trace_meta": {"rule": "demo"},
                }
            ]
        }
        ascii_out = visualize_payload(payload, "ascii")
        dot_out = visualize_payload(payload, "dot")
        self.assertIn("TREES", ascii_out)
        self.assertIn("digraph Forest", dot_out)

    def test_ascii_detail_mode_shows_m1_fields(self) -> None:
        payload = {
            "trees": [
                {
                    "root_path": "/dst/a.txt",
                    "refs": [],
                    "resolved_state": "",
                    "changerequest": [
                        {
                            "path": "/src/a.txt",
                            "action": "replace",
                            "mixed_id": "270150:100",
                            "hashtype": "sha256",
                            "hashvalue": "abc",
                            "action_order": 7,
                            "provenance_ref": "rule:demo",
                            "sidecar_ref": "sidecar:demo",
                        }
                    ],
                }
            ]
        }

        out = visualize_payload(payload, "ascii", show_m1_details=True)
        self.assertIn("order=7", out)
        self.assertIn("provenance=rule:demo", out)
        self.assertIn("sidecar=sidecar:demo", out)

    def test_dot_detail_mode_shows_m1_fields(self) -> None:
        payload = {
            "trees": [
                {
                    "root_path": "/dst/a.txt",
                    "refs": [],
                    "resolved_state": "",
                    "changerequest": [
                        {
                            "path": "/src/a.txt",
                            "action": "replace",
                            "mixed_id": "270150:100",
                            "hashtype": "sha256",
                            "hashvalue": "abc",
                            "action_order": 3,
                            "provenance_ref": "rule:abc",
                            "sidecar_ref": "sidecar:def",
                        }
                    ],
                }
            ]
        }

        out = visualize_payload(payload, "dot", show_m1_details=True)
        self.assertIn("order=3", out)
        self.assertIn("provenance=rule:abc", out)
        self.assertIn("sidecar=sidecar:def", out)

    def test_html_output_contains_tabs_and_sections(self) -> None:
        payload = {
            "warnings": ["W1"],
            "errors": ["E1"],
            "final_mapping": [
                {
                    "path": "/dst/a.txt",
                    "mixed_id": "270150:100",
                    "hashtype": "sha256",
                    "hashvalue": "abc",
                }
            ],
            "trees": [
                {
                    "root_path": "/dst/a.txt",
                    "refs": [],
                    "resolved_state": "",
                    "changerequest": [
                        {
                            "path": "/src/a.txt",
                            "action": "replace",
                            "mixed_id": "270150:100",
                            "hashtype": "sha256",
                            "hashvalue": "abc",
                        }
                    ],
                }
            ],
        }

        out = visualize_payload(payload, "html")
        self.assertIn("<!doctype html>", out.lower())
        self.assertIn('data-tab="forest-tab"', out)
        self.assertIn('data-tab="issues-tab"', out)
        self.assertIn('data-tab="mapping-tab"', out)
        self.assertIn("Wheel to zoom, drag to pan.", out)
        self.assertIn("/dst/a.txt", out)
        self.assertIn("W1", out)
        self.assertIn("E1", out)

    # --- new tests for trees format ---

    def test_ref_edges_in_dot(self) -> None:
        """Reference edges render as dashed lines in DOT output (single tree, no pack)."""
        payload = {
            "trees": [
                {
                    "root_path": "/dst/a.txt",
                    "changerequest": [
                        {"path": "/src/a.txt", "action": "replace", "mixed_id": "270150:100", "hashtype": "sha256", "hashvalue": "abc"}
                    ],
                    "refs": ["/dst/b.txt"],
                    "resolved_state": "kept",
                },
            ]
        }

        out = visualize_payload(payload, "dot")
        self.assertIn('style="dashed"', out)
        self.assertIn('color="#94a3b8"', out)
        self.assertIn("label=\"ref\"", out)

    def test_resolved_state_ascii_display(self) -> None:
        """resolved_state appears in ASCII output."""
        payload = {
            "trees": [
                {
                    "root_path": "/dst/deleted.txt",
                    "changerequest": [
                        {"path": "!", "action": "delete", "mixed_id": "270150:100", "hashtype": "sha256", "hashvalue": "0"}
                    ],
                    "refs": [],
                    "resolved_state": "deleted",
                },
                {
                    "root_path": "/dst/pending.txt",
                    "changerequest": [
                        {"path": "/src/a.txt", "action": "replace", "mixed_id": "270150:101", "hashtype": "sha256", "hashvalue": "abc"},
                        {"path": "/src/b.txt", "action": "replace", "mixed_id": "270150:102", "hashtype": "sha256", "hashvalue": "def"},
                    ],
                    "refs": [],
                    "resolved_state": "pending",
                },
            ]
        }

        out = visualize_payload(payload, "ascii")
        self.assertIn("DELETED", out)
        self.assertIn("PENDING", out)

    def test_refs_display_in_ascii(self) -> None:
        """Refs list appears in ASCII output for trees with refs."""
        payload = {
            "trees": [
                {
                    "root_path": "/dst/a.txt",
                    "changerequest": [
                        {"path": "/src/a.txt", "action": "replace", "mixed_id": "270150:100", "hashtype": "sha256", "hashvalue": "abc"}
                    ],
                    "refs": ["/dst/b.txt", "/dst/c.txt"],
                    "resolved_state": "kept",
                },
            ]
        }

        out = visualize_payload(payload, "ascii")
        self.assertIn("refs:", out)
        self.assertIn("/dst/b.txt", out)
        self.assertIn("/dst/c.txt", out)

    def test_svg_enrichment_tree_node_attributes(self) -> None:
        """SVG enrichment sets data-tree-node and data-tree-pending attributes."""
        payload = {
            "trees": [
                {
                    "root_path": "/dst/branch.txt",
                    "warning": "W_FOREST_BRANCHING",
                    "candidates": ["/src/a.txt", "/src/b.txt"],
                    "changerequest": [
                        {"path": "/src/a.txt", "action": "replace", "mixed_id": "270150:100", "hashtype": "sha256", "hashvalue": "abc"},
                        {"path": "/src/b.txt", "action": "replace", "mixed_id": "270150:101", "hashtype": "sha256", "hashvalue": "def"},
                    ],
                    "refs": [],
                    "resolved_state": "pending",
                }
            ]
        }
        # The DOT render assigns t0 to the tree node and s0/s1 to source nodes.
        # Provide a minimal SVG with matching element IDs for enrichment.
        svg_input = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<g id="t0" class="node"><title>t0</title></g>'
            '<g id="s0" class="node"><title>s0</title></g>'
            '<g id="s1" class="node"><title>s1</title></g>'
            '</svg>'
        )
        completed = subprocess.CompletedProcess(
            args=["dot", "-Tsvg"],
            returncode=0,
            stdout=svg_input.encode("utf-8"),
            stderr=b"",
        )
        with patch("modmanager.forest_visual.subprocess.run", return_value=completed):
            out = visualize_payload(payload, "svg")
        self.assertIn("data-tree-node", out)
        self.assertIn("data-tree-pending", out)
        self.assertNotIn("data-forest-node", out)
        self.assertNotIn("data-conflict", out)


    # --- P3-GUI2: SVG data-tree-refs / data-tree-referenced-by ---

    def test_svg_has_refs_attribute(self) -> None:
        """SVG enrichment sets data-tree-refs for nodes with refs."""
        trees = [
            {
                "root_path": "/game/target.png",
                "destin_mixed_id": "270150:0",
                "changerequest": [
                    {"path": "/modA/file.png", "action": "replace", "mixed_id": "270150:modA", "hashtype": "sha256", "hashvalue": ""}
                ],
                "refs": ["/modA/file.png"],
                "resolved_state": "kept",
            },
            {
                "root_path": "/modA/file.png",
                "destin_mixed_id": "270150:modA",
                "changerequest": [
                    {"path": "!", "action": "delete", "mixed_id": "270150:modA", "hashtype": "sha256", "hashvalue": "0"}
                ],
                "refs": [],
                "resolved_state": "deleted",
            },
        ]
        # The DOT render assigns t0 → /game/target.png, t1 → /modA/file.png
        # Source nodes: s0 → /modA/file.png (replace source), s1 → ! (delete source)
        svg_input = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<g id="t0" class="node"><title>t0</title></g>'
            '<g id="t1" class="node"><title>t1</title></g>'
            '<g id="s0" class="node"><title>s0</title></g>'
            '<g id="s1" class="node"><title>s1</title></g>'
            '</svg>'
        )
        completed = subprocess.CompletedProcess(
            args=["dot", "-Tsvg"],
            returncode=0,
            stdout=svg_input.encode("utf-8"),
            stderr=b"",
        )
        with patch("modmanager.forest_visual.subprocess.run", return_value=completed):
            svg = visualize_payload({"trees": trees}, "svg", show_m1_details=False)
        self.assertIn('data-tree-refs', svg)
        self.assertIn('/modA/file.png', svg)
        # t0 has refs → data-tree-refs should be /modA/file.png
        self.assertIn('data-tree-refs="/modA/file.png"', svg)

    def test_svg_has_referenced_by_attribute(self) -> None:
        """SVG enrichment sets data-tree-referenced-by for nodes that are referenced."""
        trees = [
            {
                "root_path": "/game/target.png",
                "destin_mixed_id": "270150:0",
                "changerequest": [
                    {"path": "/modA/file.png", "action": "replace", "mixed_id": "270150:modA", "hashtype": "sha256", "hashvalue": ""}
                ],
                "refs": ["/modA/file.png"],
                "resolved_state": "kept",
            },
            {
                "root_path": "/modA/file.png",
                "destin_mixed_id": "270150:modA",
                "changerequest": [
                    {"path": "!", "action": "delete", "mixed_id": "270150:modA", "hashtype": "sha256", "hashvalue": "0"}
                ],
                "refs": [],
                "resolved_state": "deleted",
            },
        ]
        svg_input = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<g id="t0" class="node"><title>t0</title></g>'
            '<g id="t1" class="node"><title>t1</title></g>'
            '<g id="s0" class="node"><title>s0</title></g>'
            '<g id="s1" class="node"><title>s1</title></g>'
            '</svg>'
        )
        completed = subprocess.CompletedProcess(
            args=["dot", "-Tsvg"],
            returncode=0,
            stdout=svg_input.encode("utf-8"),
            stderr=b"",
        )
        with patch("modmanager.forest_visual.subprocess.run", return_value=completed):
            svg = visualize_payload({"trees": trees}, "svg", show_m1_details=False)
        self.assertIn('data-tree-referenced-by', svg)
        # t1 (/modA/file.png) is referenced by t0 (/game/target.png)
        self.assertIn('data-tree-referenced-by="/game/target.png"', svg)


if __name__ == "__main__":
    unittest.main()
