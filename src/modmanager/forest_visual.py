from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
import xml.etree.ElementTree as ET
from typing import Any


class VisualizationError(Exception):
    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class GraphEdge:
    source_path: str
    target_path: str
    action: str
    mixed_id: str
    edge_type: str = "operation"


@dataclass
class GraphNode:
    root_path: str
    changerequest: list[dict[str, Any]]
    destin_mixed_id: str
    warning: str
    candidates: list[str]
    resolved_state: str
    refs: list[str]
    extra: dict[str, Any]
    raw_node_ref: dict[str, Any]


@dataclass
class GraphModel:
    nodes: dict[str, GraphNode]
    edges: list[GraphEdge]
    branching_nodes: set[str]


def _extract_forest(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        trees = payload.get("trees")
        if isinstance(trees, list):
            return trees
        forest = payload.get("forest")  # fallback for old format
        if isinstance(forest, list):
            return forest
    raise VisualizationError("invalid forest input: expected array or object with trees[]", 2)


def _build_graph_model(forest: list[dict[str, Any]]) -> GraphModel:
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    branching_nodes: set[str] = set()

    for node in forest:
        if not isinstance(node, dict):
            raise VisualizationError("invalid forest node: each node must be an object", 2)
        root_path = node.get("root_path")
        requests = node.get("changerequest")
        if not isinstance(root_path, str) or not isinstance(requests, list):
            raise VisualizationError(
                "invalid forest node: root_path must be string and changerequest must be array", 2
            )

        warning = str(node.get("warning", "")) if node.get("warning") is not None else ""
        candidates = node.get("candidates", [])
        if not isinstance(candidates, list):
            candidates = []
        destin = node.get("destin_mixed_id", "")
        if not isinstance(destin, str):
            destin = ""
        resolved_state = node.get("resolved_state", "")
        if not isinstance(resolved_state, str):
            resolved_state = ""

        # Extract refs list (used both in GraphNode and edge creation)
        raw_refs = node.get("refs", [])
        if not isinstance(raw_refs, list):
            raw_refs = []
        refs_list = [str(r) for r in raw_refs if isinstance(r, str) and r]

        extra = {
            k: v
            for k, v in node.items()
            if k not in {"root_path", "changerequest", "destin_mixed_id", "warning", "candidates", "refs", "resolved_state"}
        }

        nodes[root_path] = GraphNode(
            root_path=root_path,
            changerequest=requests,
            destin_mixed_id=destin,
            warning=warning,
            candidates=[str(c) for c in candidates],
            resolved_state=resolved_state,
            refs=refs_list,
            extra=extra,
            raw_node_ref=node,
        )

        if warning == "W_FOREST_BRANCHING" or len(requests) > 1:
            branching_nodes.add(root_path)

        # Operation edges from changerequest
        for req in requests:
            if not isinstance(req, dict):
                continue
            source = req.get("path", "")
            action = req.get("action", "")
            mixed_id = req.get("mixed_id", "")
            if not isinstance(source, str):
                source = ""
            if not isinstance(action, str):
                action = ""
            if not isinstance(mixed_id, str):
                mixed_id = ""
            edges.append(
                GraphEdge(
                    source_path=source,
                    target_path=root_path,
                    action=action,
                    mixed_id=mixed_id,
                    edge_type="operation",
                )
            )

        # Reference edges from refs
        for ref_path in refs_list:
            edges.append(
                GraphEdge(
                    source_path=root_path,
                    target_path=ref_path,
                    action="ref",
                    mixed_id="",
                    edge_type="reference",
                )
            )

    return GraphModel(nodes=nodes, edges=edges, branching_nodes=branching_nodes)


def _render_ascii(model: GraphModel, show_m1_details: bool = False) -> str:
    lines: list[str] = ["TREES"]
    for root_path in sorted(model.nodes.keys()):
        node = model.nodes[root_path]
        suffix: list[str] = []
        if root_path in model.branching_nodes:
            suffix.append("BRANCHING")
        if node.resolved_state:
            suffix.append(node.resolved_state.upper())
        if node.destin_mixed_id:
            suffix.append(node.destin_mixed_id)
        head = f"- {root_path}"
        if suffix:
            head += " [" + " | ".join(suffix) + "]"
        lines.append(head)

        if not node.changerequest:
            lines.append("  (no changerequest)")
            continue

        for idx, req in enumerate(node.changerequest, start=1):
            if not isinstance(req, dict):
                lines.append(f"  {idx}. (invalid request)")
                continue
            source = req.get("path", "")
            action = req.get("action", "")
            mixed_id = req.get("mixed_id", "")
            if not isinstance(source, str):
                source = ""
            if source == "!":
                source = "DELETE(!)"
            if not isinstance(action, str):
                action = ""
            if not isinstance(mixed_id, str):
                mixed_id = ""
            line = f"  {idx}. {action} <- {source} ({mixed_id})"
            if show_m1_details:
                action_order = req.get("action_order", 0)
                if not isinstance(action_order, int):
                    action_order = 0
                provenance_ref = req.get("provenance_ref", "404")
                sidecar_ref = req.get("sidecar_ref", "404")
                if not isinstance(provenance_ref, str) or not provenance_ref:
                    provenance_ref = "404"
                if not isinstance(sidecar_ref, str) or not sidecar_ref:
                    sidecar_ref = "404"
                line += f" [order={action_order} | provenance={provenance_ref} | sidecar={sidecar_ref}]"
            lines.append(line)

        # Show refs from raw node data
        refs = node.raw_node_ref.get("refs", [])
        if isinstance(refs, list) and refs:
            lines.append(f"  refs: {', '.join(str(r) for r in refs)}")

    return "\n".join(lines)


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _render_dot(model: GraphModel, show_m1_details: bool = False) -> str:
    lines: list[str] = ["digraph Forest {", "  bgcolor=transparent;", "  rankdir=LR;"]
    target_ids: dict[str, str] = {}
    source_ids: dict[str, str] = {}

    def target_id(path: str) -> str:
        if path not in target_ids:
            target_ids[path] = f"t{len(target_ids)}"
        return target_ids[path]

    def source_id(path: str) -> str:
        if path not in source_ids:
            source_ids[path] = f"s{len(source_ids)}"
        return source_ids[path]

    # Render target nodes (tree nodes)
    for root_path in sorted(model.nodes.keys()):
        node = model.nodes[root_path]
        nid = target_id(root_path)
        attrs = [f'label="{_dot_escape(root_path)}"', "shape=box"]

        # Coloring based on resolved_state / branching
        if root_path in model.branching_nodes or node.resolved_state == "pending":
            attrs.append('color="red"')
            attrs.append('penwidth="2"')
        elif node.resolved_state == "deleted":
            attrs.append('color="#9ca3af"')
            attrs.append('fontcolor="#9ca3af"')
        elif node.resolved_state == "failed":
            attrs.append('color="#ef4444"')
        elif node.resolved_state == "skipped":
            attrs.append('color="#fbbf24"')

        lines.append(f"  {nid} [{', '.join(attrs)}];")

    # Render operation edges
    for edge in model.edges:
        if edge.edge_type == "reference":
            continue

        src = edge.source_path if edge.source_path else "(unknown source)"
        src_label = "DELETE(!)" if src == "!" else src
        sid = source_id(src)
        shape = "diamond" if src == "!" else "ellipse"
        lines.append(f"  {sid} [label=\"{_dot_escape(src_label)}\", shape={shape}];")

        tid = target_id(edge.target_path)
        label = edge.action
        if edge.mixed_id:
            label = f"{label} | {edge.mixed_id}" if label else edge.mixed_id

        if show_m1_details:
            node = model.nodes.get(edge.target_path)
            matched_req: dict[str, Any] | None = None
            if node:
                for req in node.changerequest:
                    if not isinstance(req, dict):
                        continue
                    req_path = req.get("path", "")
                    req_action = req.get("action", "")
                    req_mid = req.get("mixed_id", "")
                    if not isinstance(req_path, str):
                        req_path = ""
                    if not isinstance(req_action, str):
                        req_action = ""
                    if not isinstance(req_mid, str):
                        req_mid = ""
                    if req_path == edge.source_path and req_action == edge.action and req_mid == edge.mixed_id:
                        matched_req = req
                        break
            if matched_req:
                action_order = matched_req.get("action_order", 0)
                if not isinstance(action_order, int):
                    action_order = 0
                provenance_ref = matched_req.get("provenance_ref", "404")
                sidecar_ref = matched_req.get("sidecar_ref", "404")
                if not isinstance(provenance_ref, str) or not provenance_ref:
                    provenance_ref = "404"
                if not isinstance(sidecar_ref, str) or not sidecar_ref:
                    sidecar_ref = "404"
                suffix = f"order={action_order} | provenance={provenance_ref} | sidecar={sidecar_ref}"
                label = f"{label}\\n{suffix}" if label else suffix

        if label:
            lines.append(f"  {sid} -> {tid} [label=\"{_dot_escape(label)}\"];")
        else:
            lines.append(f"  {sid} -> {tid};")

    # Render reference edges (dashed, between tree nodes)
    for edge in model.edges:
        if edge.edge_type != "reference":
            continue
        sid = target_id(edge.source_path)
        tid = target_id(edge.target_path)
        lines.append(f'  {sid} -> {tid} [style="dashed" color="#94a3b8" label="ref"];')

    lines.append("}")
    return "\n".join(lines)


def _render_svg_from_dot(dot_text: str, model: GraphModel | None = None) -> str:
    try:
        proc = subprocess.run(
            ["dot", "-Tsvg"],
            input=dot_text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise VisualizationError("graphviz 'dot' command not found", 4) from exc

    if proc.returncode != 0:
        msg = proc.stderr.decode("utf-8", errors="replace").strip()
        if not msg:
            msg = "graphviz dot failed"
        raise VisualizationError(f"dot to svg failed: {msg}", 5)

    svg_text = proc.stdout.decode("utf-8", errors="replace")
    if model is not None:
        svg_text = _enrich_svg_nodes(svg_text, model)
    return svg_text


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _build_dot_id_mapping(model: GraphModel) -> dict[str, str]:
    """Reconstruct the DOT node‑ID → path mapping that ``_render_dot`` produces.

    Mirrors the identical ID‑assignment logic so we can locate each node in the
    Graphviz‑generated SVG and inject interactive attributes.
    """
    target_ids: dict[str, str] = {}
    source_ids: dict[str, str] = {}

    for path in sorted(model.nodes.keys()):
        if path not in target_ids:
            target_ids[path] = f"t{len(target_ids)}"

    # Only iterate non-reference edges for source nodes
    for edge in model.edges:
        if edge.edge_type == "reference":
            continue
        src = edge.source_path if edge.source_path else "(unknown source)"
        if src not in source_ids:
            source_ids[src] = f"s{len(source_ids)}"

    mapping: dict[str, str] = {}
    for path, dot_id in target_ids.items():
        mapping[dot_id] = path
    for path, dot_id in source_ids.items():
        mapping[dot_id] = path
    return mapping


def _enrich_svg_nodes(svg_text: str, model: GraphModel) -> str:
    """Post‑process Graphviz SVG output with interactive data attributes.

    For every tree node's ``<g>`` element:
      * ``data-tree-node="<root_path>"``
      * ``<title>tree: <root_path></title>``
    For pending (branching) nodes additionally:
      * ``data-tree-pending="true"``
      * ``<desc>destin: …\\ncandidates: …</desc>``
    """
    ET.register_namespace("", "http://www.w3.org/2000/svg")

    id_mapping = _build_dot_id_mapping(model)

    # Build reverse reference index (ref → list of referencing root_paths)
    referenced_by: dict[str, list[str]] = {}
    for tree_node in model.nodes.values():
        for ref in tree_node.refs:
            if ref:
                referenced_by.setdefault(ref, []).append(tree_node.root_path)

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return svg_text  # malformed SVG → skip enrichment

    ns = "http://www.w3.org/2000/svg"
    svg_ns_g = f"{{{ns}}}g"
    svg_ns_title = f"{{{ns}}}title"
    svg_ns_desc = f"{{{ns}}}desc"

    for g_el in root.iter(svg_ns_g):
        if g_el.get("class") != "node":
            continue
        node_id = g_el.get("id", "")
        path = id_mapping.get(node_id)
        if path is None:
            continue

        # -- data-tree-node --
        g_el.set("data-tree-node", path)

        # -- data-tree-refs & data-tree-referenced-by --
        node_obj = model.nodes.get(path)
        if node_obj is not None and node_obj.refs:
            g_el.set("data-tree-refs", ",".join(node_obj.refs))
        rb = referenced_by.get(path, [])
        if rb:
            g_el.set("data-tree-referenced-by", ",".join(rb))

        # -- <title> (replace existing or insert) --
        title_el = None
        for child in g_el:
            if child.tag == svg_ns_title:
                title_el = child
                break
        if title_el is None:
            title_el = ET.Element(svg_ns_title)
            g_el.insert(0, title_el)
        title_el.text = f"tree: {path}"

        # -- pending-only extras (previously conflict) --
        if node_obj is not None and node_obj.warning == "W_FOREST_BRANCHING" and node_obj.candidates:
            g_el.set("data-tree-pending", "true")
            desc_el = None
            for child in g_el:
                if child.tag == svg_ns_desc:
                    desc_el = child
                    break
            if desc_el is None:
                desc_el = ET.Element(svg_ns_desc)
                # insert after <title>
                insert_pos = 1 if title_el is not None else 0
                g_el.insert(insert_pos, desc_el)
            desc_el.text = (
                f"destin: {node_obj.destin_mixed_id}\n"
                f"candidates: {', '.join(node_obj.candidates)}"
            )

    return ET.tostring(root, encoding="unicode")


def _render_html(payload: Any, model: GraphModel, show_m1_details: bool = False) -> str:
    warnings: list[str] = []
    errors: list[str] = []
    final_mapping: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        raw_warnings = payload.get("warnings", [])
        raw_errors = payload.get("errors", [])
        raw_final_mapping = payload.get("final_mapping", [])
        if isinstance(raw_warnings, list):
            warnings = [str(item) for item in raw_warnings]
        if isinstance(raw_errors, list):
            errors = [str(item) for item in raw_errors]
        if isinstance(raw_final_mapping, list):
            final_mapping = [item for item in raw_final_mapping if isinstance(item, dict)]

    graph_nodes: dict[str, dict[str, Any]] = {}
    graph_edges: list[dict[str, Any]] = []

    for root_path, node in model.nodes.items():
        graph_nodes[root_path] = {
            "root_path": root_path,
            "kind": "target",
            "branching": root_path in model.branching_nodes,
            "destin_mixed_id": node.destin_mixed_id,
            "warning": node.warning,
            "resolved_state": node.resolved_state,
        }

    for edge in model.edges:
        source = edge.source_path if edge.source_path else "(unknown source)"
        if source not in graph_nodes:
            graph_nodes[source] = {
                "root_path": source,
                "kind": "source",
                "branching": False,
                "destin_mixed_id": "",
                "warning": "",
                "resolved_state": "",
            }

        edge_data: dict[str, Any] = {
            "source": source,
            "target": edge.target_path,
            "action": edge.action,
            "mixed_id": edge.mixed_id,
            "edge_type": edge.edge_type,
        }

        if show_m1_details and edge.edge_type != "reference":
            target_node = model.nodes.get(edge.target_path)
            matched_req: dict[str, Any] | None = None
            if target_node:
                for req in target_node.changerequest:
                    if not isinstance(req, dict):
                        continue
                    req_path = req.get("path", "")
                    req_action = req.get("action", "")
                    req_mid = req.get("mixed_id", "")
                    if not isinstance(req_path, str):
                        req_path = ""
                    if not isinstance(req_action, str):
                        req_action = ""
                    if not isinstance(req_mid, str):
                        req_mid = ""
                    if req_path == edge.source_path and req_action == edge.action and req_mid == edge.mixed_id:
                        matched_req = req
                        break
            if matched_req:
                action_order = matched_req.get("action_order", 0)
                if not isinstance(action_order, int):
                    action_order = 0
                provenance_ref = matched_req.get("provenance_ref", "404")
                sidecar_ref = matched_req.get("sidecar_ref", "404")
                if not isinstance(provenance_ref, str) or not provenance_ref:
                    provenance_ref = "404"
                if not isinstance(sidecar_ref, str) or not sidecar_ref:
                    sidecar_ref = "404"
                edge_data["action_order"] = action_order
                edge_data["provenance_ref"] = provenance_ref
                edge_data["sidecar_ref"] = sidecar_ref

        graph_edges.append(edge_data)

    graph_payload = {
        "nodes": list(graph_nodes.values()),
        "edges": graph_edges,
    }

    warnings_items = "".join(f"<li>{_html_escape(item)}</li>" for item in warnings)
    errors_items = "".join(f"<li>{_html_escape(item)}</li>" for item in errors)

    final_mapping_rows: list[str] = []
    for entry in final_mapping:
        final_mapping_rows.append(
            "<tr>"
            f"<td>{_html_escape(str(entry.get('path', '')))}</td>"
            f"<td>{_html_escape(str(entry.get('mixed_id', '')))}</td>"
            f"<td>{_html_escape(str(entry.get('hashtype', '')))}</td>"
            f"<td>{_html_escape(str(entry.get('hashvalue', '')))}</td>"
            "</tr>"
        )
    final_mapping_table = "".join(final_mapping_rows)

    graph_json = json.dumps(graph_payload, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Tree Mapping Viewer</title>
    <style>
        :root {{
            --bg: #f3f4f6;
            --panel: #ffffff;
            --line: #d1d5db;
            --text: #111827;
            --muted: #4b5563;
            --accent: #0f766e;
            --danger: #b91c1c;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            font-family: "Iosevka Aile", "IBM Plex Sans", "Noto Sans", sans-serif;
            background: radial-gradient(circle at top left, #e0f2fe 0%, var(--bg) 40%);
            color: var(--text);
        }}
        .layout {{
            max-width: 1300px;
            margin: 0 auto;
            padding: 16px;
        }}
        .tabs {{
            display: flex;
            gap: 8px;
            margin-bottom: 12px;
            flex-wrap: wrap;
        }}
        .tab-btn {{
            border: 1px solid var(--line);
            background: var(--panel);
            color: var(--text);
            padding: 8px 12px;
            border-radius: 999px;
            cursor: pointer;
            font-weight: 600;
        }}
        .tab-btn.active {{
            background: var(--accent);
            color: #ffffff;
            border-color: var(--accent);
        }}
        .tab-panel {{
            display: none;
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 12px;
            min-height: 72vh;
        }}
        .tab-panel.active {{
            display: block;
        }}
        .toolbar {{
            display: flex;
            gap: 8px;
            margin-bottom: 10px;
            flex-wrap: wrap;
            align-items: center;
            color: var(--muted);
        }}
        .toolbar button {{
            border: 1px solid var(--line);
            background: #f9fafb;
            padding: 6px 10px;
            border-radius: 8px;
            cursor: pointer;
        }}
        #forest-stage {{
            width: 100%;
            height: calc(72vh - 60px);
            border: 1px solid var(--line);
            border-radius: 10px;
            background: #ffffff;
            touch-action: none;
            user-select: none;
        }}
        .issue-group h3 {{ margin: 8px 0; }}
        .issue-group ul {{ margin-top: 4px; }}
        .error-title {{ color: var(--danger); }}
        table {{
            border-collapse: collapse;
            width: 100%;
            font-size: 13px;
        }}
        th, td {{
            border: 1px solid var(--line);
            padding: 6px;
            text-align: left;
            vertical-align: top;
            word-break: break-word;
        }}
        th {{ background: #f3f4f6; }}
    </style>
</head>
<body>
    <div class="layout">
        <div class="tabs">
            <button class="tab-btn active" data-tab="forest-tab">Tree Map</button>
            <button class="tab-btn" data-tab="issues-tab">Warnings / Errors</button>
            <button class="tab-btn" data-tab="mapping-tab">Final Mapping</button>
        </div>

        <section id="forest-tab" class="tab-panel active">
            <div class="toolbar">
                <button type="button" id="zoom-in">Zoom In</button>
                <button type="button" id="zoom-out">Zoom Out</button>
                <button type="button" id="reset-view">Reset</button>
                <span>Wheel to zoom, drag to pan.</span>
            </div>
            <svg id="forest-stage" viewBox="0 0 1200 800" aria-label="tree-mapping">
                <g id="forest-camera"></g>
            </svg>
        </section>

        <section id="issues-tab" class="tab-panel">
            <div class="issue-group">
                <h3>Warnings ({len(warnings)})</h3>
                <ul>{warnings_items or '<li>(none)</li>'}</ul>
            </div>
            <div class="issue-group">
                <h3 class="error-title">Errors ({len(errors)})</h3>
                <ul>{errors_items or '<li>(none)</li>'}</ul>
            </div>
        </section>

        <section id="mapping-tab" class="tab-panel">
            <table>
                <thead>
                    <tr>
                        <th>path</th>
                        <th>mixed_id</th>
                        <th>hashtype</th>
                        <th>hashvalue</th>
                    </tr>
                </thead>
                <tbody>
                    {final_mapping_table or '<tr><td colspan="4">(none)</td></tr>'}
                </tbody>
            </table>
        </section>
    </div>

    <script>
        const graph = {graph_json};

        const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
        const tabPanels = Array.from(document.querySelectorAll(".tab-panel"));
        for (const button of tabButtons) {{
            button.addEventListener("click", () => {{
                const target = button.getAttribute("data-tab");
                for (const b of tabButtons) b.classList.remove("active");
                for (const p of tabPanels) p.classList.remove("active");
                button.classList.add("active");
                const panel = document.getElementById(target);
                if (panel) panel.classList.add("active");
            }});
        }}

        const svg = document.getElementById("forest-stage");
        const camera = document.getElementById("forest-camera");

        const state = {{ scale: 1, tx: 0, ty: 0, dragging: false, px: 0, py: 0 }};
        function updateTransform() {{
            camera.setAttribute("transform", `translate(${{state.tx}} ${{state.ty}}) scale(${{state.scale}})`);
        }}

        function clampScale(value) {{
            if (value < 0.2) return 0.2;
            if (value > 3.5) return 3.5;
            return value;
        }}

        function zoomBy(factor, cx, cy) {{
            const next = clampScale(state.scale * factor);
            const worldX = (cx - state.tx) / state.scale;
            const worldY = (cy - state.ty) / state.scale;
            state.scale = next;
            state.tx = cx - worldX * state.scale;
            state.ty = cy - worldY * state.scale;
            updateTransform();
        }}

        svg.addEventListener("wheel", (event) => {{
            event.preventDefault();
            const rect = svg.getBoundingClientRect();
            const cx = event.clientX - rect.left;
            const cy = event.clientY - rect.top;
            const factor = event.deltaY < 0 ? 1.08 : 0.92;
            zoomBy(factor, cx, cy);
        }});

        svg.addEventListener("pointerdown", (event) => {{
            state.dragging = true;
            state.px = event.clientX;
            state.py = event.clientY;
            svg.setPointerCapture(event.pointerId);
        }});
        svg.addEventListener("pointermove", (event) => {{
            if (!state.dragging) return;
            state.tx += event.clientX - state.px;
            state.ty += event.clientY - state.py;
            state.px = event.clientX;
            state.py = event.clientY;
            updateTransform();
        }});
        svg.addEventListener("pointerup", () => {{
            state.dragging = false;
        }});

        document.getElementById("zoom-in").addEventListener("click", () => zoomBy(1.2, 400, 250));
        document.getElementById("zoom-out").addEventListener("click", () => zoomBy(0.85, 400, 250));
        document.getElementById("reset-view").addEventListener("click", () => {{
            state.scale = 1;
            state.tx = 0;
            state.ty = 0;
            updateTransform();
        }});

        const nodesByPath = new Map();
        for (const node of graph.nodes) nodesByPath.set(node.root_path, node);

        const incoming = new Map();
        for (const node of graph.nodes) incoming.set(node.root_path, []);
        for (const edge of graph.edges) {{
            if (!incoming.has(edge.target)) incoming.set(edge.target, []);
            incoming.get(edge.target).push(edge.source);
        }}

        const depth = new Map();
        for (const node of graph.nodes) depth.set(node.root_path, 0);
        for (let i = 0; i < graph.nodes.length; i += 1) {{
            let changed = false;
            for (const edge of graph.edges) {{
                const srcDepth = depth.get(edge.source) || 0;
                const dstDepth = depth.get(edge.target) || 0;
                if (dstDepth < srcDepth + 1) {{
                    depth.set(edge.target, srcDepth + 1);
                    changed = true;
                }}
            }}
            if (!changed) break;
        }}

        const layers = new Map();
        for (const node of graph.nodes) {{
            const d = depth.get(node.root_path) || 0;
            if (!layers.has(d)) layers.set(d, []);
            layers.get(d).push(node.root_path);
        }}
        for (const arr of layers.values()) arr.sort((a, b) => a.localeCompare(b));

        const positions = new Map();
        const nodeWidth = 220;
        const nodeHeight = 44;
        const layerGapX = 280;
        const layerGapY = 86;
        let maxY = 0;
        let maxX = 0;
        for (const [d, paths] of layers.entries()) {{
            const x = 30 + d * layerGapX;
            for (let i = 0; i < paths.length; i += 1) {{
                const y = 30 + i * layerGapY;
                positions.set(paths[i], {{ x, y }});
                if (y > maxY) maxY = y;
            }}
            if (x > maxX) maxX = x;
        }}
        svg.setAttribute("viewBox", `0 0 ${{Math.max(1200, maxX + 320)}} ${{Math.max(800, maxY + 180)}}`);

        function el(name, attrs = {{}}) {{
            const node = document.createElementNS("http://www.w3.org/2000/svg", name);
            for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
            return node;
        }}

        for (const edge of graph.edges) {{
            const sp = positions.get(edge.source);
            const tp = positions.get(edge.target);
            if (!sp || !tp) continue;
            const sx = sp.x + nodeWidth;
            const sy = sp.y + nodeHeight / 2;
            const tx = tp.x;
            const ty = tp.y + nodeHeight / 2;
            const cx1 = sx + 48;
            const cx2 = tx - 48;
            const isRef = edge.edge_type === "reference";
            const path = el("path", {{
                d: `M ${{sx}} ${{sy}} C ${{cx1}} ${{sy}}, ${{cx2}} ${{ty}}, ${{tx}} ${{ty}}`,
                stroke: isRef ? "#94a3b8" : "#64748b",
                "stroke-width": 1.4,
                fill: "none",
                ...(isRef ? {{ "stroke-dasharray": "5,5" }} : {{}}),
            }});
            camera.appendChild(path);

            let label = edge.action || "";
            if (edge.mixed_id) label = label ? `${{label}} | ${{edge.mixed_id}}` : edge.mixed_id;
            if (edge.action_order !== undefined) {{
                label += `\\norder=${{edge.action_order}} provenance=${{edge.provenance_ref || "404"}} sidecar=${{edge.sidecar_ref || "404"}}`;
            }}
            if (label) {{
                const text = el("text", {{
                    x: (sx + tx) / 2,
                    y: (sy + ty) / 2 - 6,
                    "text-anchor": "middle",
                    "font-size": 10,
                    fill: isRef ? "#94a3b8" : "#334155",
                }});
                for (const [idx, line] of label.split("\\n").entries()) {{
                    const tspan = el("tspan", {{ x: (sx + tx) / 2, dy: idx === 0 ? 0 : 11 }});
                    tspan.textContent = line;
                    text.appendChild(tspan);
                }}
                camera.appendChild(text);
            }}
        }}

        for (const node of graph.nodes) {{
            const p = positions.get(node.root_path);
            if (!p) continue;
            const isBranch = !!node.branching;
            const isDelete = node.root_path === "!";
            const rs = node.resolved_state || "";
            let fillColor = node.kind === "target" ? "#ecfeff" : "#f8fafc";
            let strokeColor = "#0f172a";
            let strokeWidth = 1;
            if (isDelete) {{
                fillColor = "#fef2f2";
            }} else if (rs === "pending") {{
                strokeColor = "#b91c1c";
                strokeWidth = 2.2;
            }} else if (rs === "deleted") {{
                fillColor = "#f3f4f6";
                strokeColor = "#9ca3af";
            }} else if (rs === "failed") {{
                strokeColor = "#ef4444";
            }} else if (rs === "skipped") {{
                strokeColor = "#fbbf24";
            }}
            if (isBranch) {{
                strokeColor = "#b91c1c";
                strokeWidth = 2.2;
            }}
            const rect = el("rect", {{
                x: p.x,
                y: p.y,
                width: nodeWidth,
                height: nodeHeight,
                rx: 7,
                ry: 7,
                fill: fillColor,
                stroke: strokeColor,
                "stroke-width": strokeWidth,
            }});
            camera.appendChild(rect);

            const title = el("text", {{ x: p.x + 8, y: p.y + 18, "font-size": 11, fill: "#111827" }});
            title.textContent = node.root_path === "!" ? "DELETE(!)" : node.root_path;
            camera.appendChild(title);

            let subtitleText = node.kind === "target" ? "tree" : "source";
            if (node.destin_mixed_id) subtitleText += ` | ${{node.destin_mixed_id}}`;
            if (isBranch) subtitleText += " | BRANCHING";
            if (rs) subtitleText += ` | ${{rs.toUpperCase()}}`;

            const subtitle = el("text", {{ x: p.x + 8, y: p.y + 33, "font-size": 10, fill: "#475569" }});
            subtitle.textContent = subtitleText;
            camera.appendChild(subtitle);
        }}
    </script>
</body>
</html>
"""


def visualize_payload(payload: Any, output_format: str, show_m1_details: bool = False) -> str:
    fmt = output_format.strip().lower()
    forest = _extract_forest(payload)
    model = _build_graph_model(forest)

    if fmt == "ascii":
        return _render_ascii(model, show_m1_details=show_m1_details)
    if fmt == "dot":
        return _render_dot(model, show_m1_details=show_m1_details)
    if fmt == "svg":
        return _render_svg_from_dot(
            _render_dot(model, show_m1_details=show_m1_details),
            model=model,
        )
    if fmt == "html":
        return _render_html(payload, model, show_m1_details=show_m1_details)

    raise VisualizationError(f"unsupported visualization format: {output_format}", 3)


__all__ = ["VisualizationError", "visualize_payload"]
