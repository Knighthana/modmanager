from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from modmanager.forest_visual import VisualizationError, visualize_payload


class ForestVisualTests(unittest.TestCase):
    def test_ascii_marks_branching_and_delete(self) -> None:
        payload = {
            "forest": [
                {
                    "path": "/dst/a.txt",
                    "warning": "W_FOREST_BRANCHING",
                    "changerequest": [
                        {"path": "!", "action": "delete", "mixed_id": "270150:100", "hashtype": "sha256", "hashvalue": "0"},
                        {"path": "/src/a.txt", "action": "replace", "mixed_id": "270150:101", "hashtype": "sha256", "hashvalue": "abc"},
                    ],
                }
            ]
        }

        out = visualize_payload(payload, "ascii")
        self.assertIn("BRANCHING", out)
        self.assertIn("DELETE(!)", out)

    def test_dot_output_contains_graph_header(self) -> None:
        payload = {
            "forest": [
                {
                    "path": "/dst/a.txt",
                    "changerequest": [
                        {"path": "/src/a.txt", "action": "replace", "mixed_id": "270150:100", "hashtype": "sha256", "hashvalue": "abc"}
                    ],
                    "trace_meta": {"rule": "demo"},
                }
            ]
        }

        out = visualize_payload(payload, "dot")
        self.assertIn("digraph Forest", out)
        self.assertIn("/dst/a.txt", out)

    def test_dot_escapes_special_characters(self) -> None:
        payload = {
            "forest": [
                {
                    "path": '/dst/"a\\b\n中.txt',
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
            "forest": [
                {
                    "path": "/dst/a.txt",
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
            visualize_payload({"forest": []}, "mermaid")
        self.assertEqual(ctx.exception.code, 3)

    def test_svg_missing_dot_raises_code_4(self) -> None:
        payload = {"forest": [{"path": "/dst/a.txt", "changerequest": []}]}
        with patch("modmanager.forest_visual.subprocess.run", side_effect=FileNotFoundError()):
            with self.assertRaises(VisualizationError) as ctx:
                visualize_payload(payload, "svg")
        self.assertEqual(ctx.exception.code, 4)

    def test_unknown_extension_fields_are_non_fatal(self) -> None:
        payload = {
            "forest": [
                {
                    "path": "/dst/a.txt",
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
        self.assertIn("FOREST", ascii_out)
        self.assertIn("digraph Forest", dot_out)

    def test_ascii_detail_mode_shows_m1_fields(self) -> None:
        payload = {
            "forest": [
                {
                    "path": "/dst/a.txt",
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
            "forest": [
                {
                    "path": "/dst/a.txt",
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
            "forest": [
                {
                    "path": "/dst/a.txt",
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


if __name__ == "__main__":
    unittest.main()
