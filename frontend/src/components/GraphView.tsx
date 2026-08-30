import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { useEffect, useRef } from "react";
import { expandCompanyNode, expandPersonNode } from "../api/client";
import type { Graph, GraphDelta, GraphNode } from "../api/types";

interface GraphViewProps {
  graph: Graph;
  onError: (message: string) => void;
}

function toElements(graph: Pick<Graph, "nodes" | "edges" | "indicators">): ElementDefinition[] {
  const sharedPartners = new Set(graph.indicators.shared_partner_person_ids);
  const nodeEls: ElementDefinition[] = graph.nodes.map((node) => ({
    data: {
      id: node.id,
      label: node.label,
      nodeType: node.node_type,
      cnpj: node.cnpj,
      isSharedPartner: sharedPartners.has(node.id),
      isSharedAddress: node.shared_address_company_count != null,
    },
  }));
  const edgeEls: ElementDefinition[] = graph.edges.map((edge) => ({
    data: {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label ?? "",
    },
  }));
  return [...nodeEls, ...edgeEls];
}

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function buildStylesheet() {
  const primary = cssVar("--color-primary");
  const success = cssVar("--color-success-text");
  const warning = cssVar("--color-warning-text");
  const danger = cssVar("--color-danger");
  const textMuted = cssVar("--color-text-muted");
  const text = cssVar("--color-text");

  return [
    {
      selector: "node",
      style: {
        label: "data(label)",
        color: text,
        "font-size": 10,
        "text-wrap": "wrap" as const,
        "text-max-width": "80px",
        "text-valign": "bottom" as const,
        "text-margin-y": 4,
        width: 28,
        height: 28,
      },
    },
    {
      selector: "node[nodeType = 'company']",
      style: { "background-color": primary, shape: "round-rectangle" as const },
    },
    {
      selector: "node[nodeType = 'person']",
      style: { "background-color": success, shape: "ellipse" as const },
    },
    {
      selector: "node[?isSharedPartner]",
      style: { "border-width": 3, "border-color": warning },
    },
    {
      selector: "node[?isSharedAddress]",
      style: { "border-width": 3, "border-color": danger, "border-style": "dashed" as const },
    },
    {
      selector: "edge",
      style: {
        width: 1.5,
        "line-color": textMuted,
        "target-arrow-color": textMuted,
        "target-arrow-shape": "triangle" as const,
        "curve-style": "bezier" as const,
        label: "data(label)",
        color: text,
        "font-size": 8,
        "text-rotation": "autorotate" as const,
      },
    },
  ];
}

function deltaToElements(delta: GraphDelta, existingIds: Set<string>): ElementDefinition[] {
  const nodeEls: ElementDefinition[] = delta.nodes
    .filter((n) => !existingIds.has(n.id))
    .map((node: GraphNode) => ({
      data: {
        id: node.id,
        label: node.label,
        nodeType: node.node_type,
        cnpj: node.cnpj,
        isSharedPartner: false,
        isSharedAddress: node.shared_address_company_count != null,
      },
    }));
  const edgeEls: ElementDefinition[] = delta.edges
    .filter((e) => !existingIds.has(e.id))
    .map((edge) => ({
      data: { id: edge.id, source: edge.source, target: edge.target, label: edge.label ?? "" },
    }));
  return [...nodeEls, ...edgeEls];
}

export function GraphView({ graph, onError }: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const expandingRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: toElements(graph),
      style: buildStylesheet(),
      layout: { name: "cose", animate: false },
    });

    const handleThemeChange = () => {
      cy.style(buildStylesheet()).update();
    };
    window.addEventListener("themechange", handleThemeChange);

    cy.on("tap", "node", async (evt) => {
      const node = evt.target;
      const id = node.id() as string;
      if (expandingRef.current.has(id)) return;
      expandingRef.current.add(id);
      node.addClass("expanding");

      try {
        const nodeType = node.data("nodeType") as "company" | "person";
        const delta =
          nodeType === "company" ? await expandCompanyNode(id) : await expandPersonNode(id);
        const existingIds = new Set(cy.elements().map((el) => el.id()));
        const newElements = deltaToElements(delta, existingIds);
        if (newElements.length > 0) {
          cy.add(newElements);
          cy.layout({ name: "cose", animate: true, fit: true }).run();
        }
      } catch (err) {
        onError(err instanceof Error ? err.message : "Falha ao expandir o nó");
      } finally {
        node.removeClass("expanding");
        expandingRef.current.delete(id);
      }
    });

    cyRef.current = cy;

    const handleResize = () => {
      cy.resize();
      cy.fit();
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("themechange", handleThemeChange);
      cy.destroy();
      cyRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph.root_cnpj]);

  return <div ref={containerRef} className="graph-container" />;
}
