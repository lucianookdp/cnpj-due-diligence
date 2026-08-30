import math
import uuid
from datetime import UTC, datetime
from html import escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session
from weasyprint import HTML

from app.core.config import Settings
from app.repositories import graph_repository
from app.schemas.company import CompanyOut
from app.schemas.graph import GraphEdgeOut, GraphNodeOut
from app.services import graph_view

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=True)

_SVG_SIZE = 900
_SVG_RADIUS = 380
_COMPANY_COLOR = "#4f46e5"
_PERSON_COLOR = "#16a34a"
_EDGE_COLOR = "#9ca3af"

# A static radial layout only stays legible up to a couple dozen nodes — a
# large company (e.g. hundreds of bank branches) would otherwise produce an
# unreadable wall of overlapping labels with no way to zoom or pan, unlike
# the interactive web view. Direct neighbors of the root are kept first,
# since they're the most relevant relationships to show in a report.
_MAX_PDF_GRAPH_NODES = 40


def _score_colors(score: int) -> dict[str, str]:
    if score >= 60:
        return {"score_bg": "#fef2f2", "score_fg": "#991b1b", "score_border": "#fecaca"}
    if score >= 30:
        return {"score_bg": "#fffbeb", "score_fg": "#92400e", "score_border": "#fde68a"}
    return {"score_bg": "#f0fdf4", "score_fg": "#166534", "score_border": "#bbf7d0"}


def _truncate(label: str, max_len: int = 24) -> str:
    return label if len(label) <= max_len else label[: max_len - 1] + "…"


def _build_graph_svg(
    nodes: list[GraphNodeOut], edges: list[GraphEdgeOut], root_id: uuid.UUID
) -> str:
    """A plain radial layout: root at the center, everything else spaced
    evenly around it. WeasyPrint has no JS/layout engine to run something
    like Cytoscape's cose layout, so this trades layout quality for being
    fully deterministic and dependency-free — good enough for a printed
    snapshot, not meant to replace the interactive graph in the app.
    """
    center = _SVG_SIZE / 2
    others = sorted((n for n in nodes if n.id != root_id), key=lambda n: n.label)
    positions: dict[uuid.UUID, tuple[float, float]] = {root_id: (center, center)}

    count = len(others)
    for i, node in enumerate(others):
        angle = (2 * math.pi * i / count) - (math.pi / 2) if count else 0.0
        positions[node.id] = (
            center + _SVG_RADIUS * math.cos(angle),
            center + _SVG_RADIUS * math.sin(angle),
        )

    svg_open = (
        f'<svg viewBox="0 0 {_SVG_SIZE} {_SVG_SIZE}" xmlns="http://www.w3.org/2000/svg" '
        f'font-family="Helvetica, Arial, sans-serif">'
    )
    parts = [svg_open]

    for edge in edges:
        if edge.source not in positions or edge.target not in positions:
            continue
        x1, y1 = positions[edge.source]
        x2, y2 = positions[edge.target]
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{_EDGE_COLOR}" stroke-width="1.5" />'
        )

    nodes_by_id = {n.id: n for n in nodes}
    for node_id, (x, y) in positions.items():
        node = nodes_by_id[node_id]
        is_root = node_id == root_id
        radius = 30 if is_root else 20
        color = _COMPANY_COLOR if node.node_type == "company" else _PERSON_COLOR
        if node.node_type == "company":
            parts.append(
                f'<rect x="{x - radius:.1f}" y="{y - radius:.1f}" '
                f'width="{radius * 2}" height="{radius * 2}" rx="6" fill="{color}" />'
            )
        else:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{color}" />')
        label = escape(_truncate(node.label))
        parts.append(
            f'<text x="{x:.1f}" y="{y + radius + 14:.1f}" text-anchor="middle" '
            f'font-size="11" fill="#111827">{label}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def _cap_nodes_for_pdf(
    nodes: list[GraphNodeOut], edges: list[GraphEdgeOut], root_id: uuid.UUID
) -> tuple[list[GraphNodeOut], list[GraphEdgeOut], int]:
    """Returns (nodes, edges, total_before_truncation)."""
    total = len(nodes)
    if total <= _MAX_PDF_GRAPH_NODES:
        return nodes, edges, total

    root_neighbors = {
        (edge.target if edge.source == root_id else edge.source)
        for edge in edges
        if root_id in (edge.source, edge.target)
    }
    others = [n for n in nodes if n.id != root_id]
    direct = sorted((n for n in others if n.id in root_neighbors), key=lambda n: n.label)
    indirect = sorted((n for n in others if n.id not in root_neighbors), key=lambda n: n.label)

    budget = _MAX_PDF_GRAPH_NODES - 1
    kept_others = (direct + indirect)[:budget]
    kept_ids = {root_id, *(n.id for n in kept_others)}

    kept_nodes = [n for n in nodes if n.id in kept_ids]
    kept_edges = [e for e in edges if e.source in kept_ids and e.target in kept_ids]
    return kept_nodes, kept_edges, total


def render_dossier_pdf(db: Session, company: CompanyOut, settings: Settings) -> bytes:
    node_ids = graph_repository.get_reachable_node_ids(
        db,
        company.id,
        max_depth=settings.graph_max_depth * 2,
        max_nodes=settings.graph_max_nodes_per_level * (settings.graph_max_depth + 1),
    )
    nodes, edges, _indicators = graph_view.render_subgraph(
        db, node_ids, settings.shared_address_threshold
    )
    nodes, edges, total_nodes = _cap_nodes_for_pdf(nodes, edges, company.id)
    # Only worth a page if the root actually has relationships worth drawing —
    # a lone node with no edges is just noise on an otherwise-full report.
    graph_svg = _build_graph_svg(nodes, edges, company.id) if len(nodes) > 1 else None

    template = _env.get_template("dossier.html")
    html = template.render(
        company=company,
        risk_score=company.risk_score,
        generated_at=datetime.now(UTC),
        graph_svg=graph_svg,
        graph_shown_count=len(nodes),
        graph_total_count=total_nodes,
        **_score_colors(company.risk_score.score),
    )
    return HTML(string=html).write_pdf()
