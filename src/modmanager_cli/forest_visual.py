from __future__ import annotations

from dataclasses import dataclass
import subprocess
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


@dataclass
class GraphNode:
    path: str
    changerequest: list[dict[str, Any]]
    destin_mixed_id: str
    warning: str
    candidates: list[str]
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
        forest = payload.get("forest")
        if isinstance(forest, list):
            return forest
    raise VisualizationError("invalid forest input: expected array or object with forest[]", 2)


def _build_graph_model(forest: list[dict[str, Any]]) -> GraphModel:
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []
    branching_nodes: set[str] = set()

    for node in forest:
        if not isinstance(node, dict):
            raise VisualizationError("invalid forest node: each node must be an object", 2)
        path = node.get("path")
        requests = node.get("changerequest")
        if not isinstance(path, str) or not isinstance(requests, list):
            raise VisualizationError("invalid forest node: path must be string and changerequest must be array", 2)

        warning = str(node.get("warning", "")) if node.get("warning") is not None else ""
        candidates = node.get("candidates", [])
        if not isinstance(candidates, list):
            candidates = []
        destin = node.get("destin_mixed_id", "")
        if not isinstance(destin, str):
            destin = ""

        extra = {
            k: v
            for k, v in node.items()
            if k not in {"path", "changerequest", "destin_mixed_id", "warning", "candidates"}
        }

        nodes[path] = GraphNode(
            path=path,
            changerequest=requests,
            destin_mixed_id=destin,
            warning=warning,
            candidates=[str(c) for c in candidates],
            extra=extra,
            raw_node_ref=node,
        )

        if warning == "W_FOREST_BRANCHING" or len(requests) > 1:
            branching_nodes.add(path)

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
            edges.append(GraphEdge(source_path=source, target_path=path, action=action, mixed_id=mixed_id))

    return GraphModel(nodes=nodes, edges=edges, branching_nodes=branching_nodes)


def _render_ascii(model: GraphModel, show_m1_details: bool = False) -> str:
    lines: list[str] = ["FOREST"]
    for path in sorted(model.nodes.keys()):
        node = model.nodes[path]
        suffix: list[str] = []
        if path in model.branching_nodes:
            suffix.append("BRANCHING")
        if node.destin_mixed_id:
            suffix.append(node.destin_mixed_id)
        head = f"- {path}"
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
    return "\n".join(lines)


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _render_dot(model: GraphModel, show_m1_details: bool = False) -> str:
    lines: list[str] = ["digraph Forest {", "  rankdir=LR;"]
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

    for path in sorted(model.nodes.keys()):
        node = model.nodes[path]
        nid = target_id(path)
        attrs = [f'label="{_dot_escape(path)}"', "shape=box"]
        if path in model.branching_nodes:
            attrs.append('color="red"')
            attrs.append('penwidth="2"')
        lines.append(f"  {nid} [{', '.join(attrs)}];")

    for edge in model.edges:
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

    lines.append("}")
    return "\n".join(lines)


def _render_svg_from_dot(dot_text: str) -> str:
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

    return proc.stdout.decode("utf-8", errors="replace")


def visualize_payload(payload: Any, output_format: str, show_m1_details: bool = False) -> str:
    fmt = output_format.strip().lower()
    forest = _extract_forest(payload)
    model = _build_graph_model(forest)

    if fmt == "ascii":
        return _render_ascii(model, show_m1_details=show_m1_details)
    if fmt == "dot":
        return _render_dot(model, show_m1_details=show_m1_details)
    if fmt == "svg":
        return _render_svg_from_dot(_render_dot(model, show_m1_details=show_m1_details))

    raise VisualizationError(f"unsupported visualization format: {output_format}", 3)


__all__ = ["VisualizationError", "visualize_payload"]
