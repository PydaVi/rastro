from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import Dict, List


COLORS = {
    "bg": "#0a0a08",
    "surface": "#111110",
    "border": "#2a2a26",
    "text": "#f0ede4",
    "muted": "#b8b4a8",
    "accent": "#c8f04a",
    "accent2": "#f04a2a",
    "accent3": "#4af0c8",
    "amber": "#f0b84a",
    "mono_font": "IBM Plex Mono",
    "sans_font": "Syne",
}


def render_attack_graph_html(report_data: Dict, output_dir: Path) -> None:
    graph_data = build_graph_data(report_data)
    html = _build_html(report_data, graph_data)
    (output_dir / "attack_graph.html").write_text(html)


def build_graph_data(report: Dict) -> Dict:
    raw_graph = report.get("attack_graph") or {}
    raw_nodes = raw_graph.get("nodes", [])
    links = raw_graph.get("edges", [])

    objective_target = (report.get("executive_summary") or {}).get("final_resource")
    objective_id = f"resource:{objective_target}" if objective_target else None
    failed_roles = set((report.get("path_memory") or {}).get("failed_assume_roles", []))
    rejected_roles = set((report.get("choice_summary") or {}).get("rejected_roles", []))
    dead_end_ids = {f"identity:{role}" for role in failed_roles.union(rejected_roles)}

    nodes_by_id: Dict[str, Dict] = {}
    for node in raw_nodes:
        node_id = node.get("id")
        if not node_id:
            continue
        if node_id not in nodes_by_id:
            nodes_by_id[node_id] = {
                "id": node_id,
                "label": node.get("label"),
                "type": node.get("type", "resource"),
                "step": node.get("step"),
                "mitre_id": node.get("mitre_id"),
                "depth": node.get("depth", 0),
            }
        else:
            if node.get("type") == "dead_end":
                nodes_by_id[node_id]["type"] = "dead_end"

    nodes = list(nodes_by_id.values())
    for node in nodes:
        node_id = node.get("id")
        node_type = node.get("type")
        if objective_id and node_id == objective_id:
            node_type = "objective"
        elif node_id in dead_end_ids:
            node_type = "dead_end"
        node["type"] = node_type or "resource"

    _assign_depths(nodes, links, root_id=_infer_root_id(report, nodes))
    return {"nodes": nodes, "links": links}


def _infer_root_id(report: Dict, nodes: List[Dict]) -> str | None:
    initial_identity = (report.get("executive_summary") or {}).get("initial_identity")
    if initial_identity:
        candidate = f"identity:{initial_identity}"
        if any(node.get("id") == candidate for node in nodes):
            return candidate
    return None


def _assign_depths(nodes: List[Dict], links: List[Dict], root_id: str | None) -> None:
    node_map = {node["id"]: node for node in nodes if "id" in node}
    incoming = {node_id: 0 for node_id in node_map}
    adjacency: Dict[str, List[str]] = {node_id: [] for node_id in node_map}

    for link in links:
        src = link.get("source")
        tgt = link.get("target")
        if src in node_map and tgt in node_map:
            adjacency[src].append(tgt)
            incoming[tgt] += 1

    roots = [root_id] if root_id else [node_id for node_id, count in incoming.items() if count == 0]
    depths: Dict[str, int] = {}

    queue = [(root, 0) for root in roots if root]
    while queue:
        current, depth = queue.pop(0)
        if current in depths and depth >= depths[current]:
            continue
        depths[current] = depth
        for nxt in adjacency.get(current, []):
            queue.append((nxt, depth + 1))

    for node_id, node in node_map.items():
        node["depth"] = depths.get(node_id, 0)


def _build_html(report: Dict, graph: Dict) -> str:
    report_json = json.dumps(report, ensure_ascii=False)
    graph_json = json.dumps(graph, ensure_ascii=False)

    template = Template(
        """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Rastro Attack Path</title>
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=IBM+Plex+Mono:wght@400;500" rel="stylesheet" />
  <style>
    :root {
      --bg: $BG;
      --surface: $SURFACE;
      --border: $BORDER;
      --text: $TEXT;
      --muted: $MUTED;
      --accent: $ACCENT;
      --accent2: $ACCENT2;
      --accent3: $ACCENT3;
      --amber: $AMBER;
      --mono: "$MONO", monospace;
      --sans: "$SANS", sans-serif;
    }
    html, body {
      height: 100%;
    }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: var(--sans);
    }
    #header {
      padding: 16px 24px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
    }
    #meta {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    #meta .title {
      font-size: 20px;
      font-weight: 800;
    }
    #meta .subtitle {
      font-family: var(--mono);
      font-size: 12px;
      color: var(--muted);
    }
    #controls {
      display: flex;
      gap: 8px;
    }
    button {
      background: var(--surface);
      color: var(--text);
      border: 1px solid var(--border);
      padding: 8px 12px;
      font-family: var(--mono);
      font-size: 12px;
      cursor: pointer;
    }
    #graph-container {
      position: relative;
      height: calc(100vh - 72px);
    }
    #attack-graph {
      width: 100%;
      height: 100%;
    }
    #tooltip {
      position: absolute;
      display: none;
      background: var(--surface);
      border: 1px solid var(--border);
      padding: 8px;
      font-family: var(--mono);
      font-size: 12px;
      color: var(--text);
      pointer-events: none;
      z-index: 10;
      max-width: 260px;
    }
    #detail-panel {
      position: absolute;
      top: 0;
      right: 0;
      width: 320px;
      height: 100%;
      background: var(--surface);
      border-left: 1px solid var(--border);
      transform: translateX(100%);
      transition: transform 200ms ease;
      z-index: 5;
      padding: 16px;
      box-sizing: border-box;
    }
    #detail-panel.open {
      transform: translateX(0);
    }
    #panel-content {
      font-family: var(--mono);
      font-size: 12px;
      color: var(--text);
      white-space: pre-wrap;
    }
    #close-panel {
      position: absolute;
      top: 12px;
      right: 12px;
      background: transparent;
      border: none;
      color: var(--muted);
      font-size: 18px;
      cursor: pointer;
    }
  </style>
</head>
<body>
  <div id="header">
    <div id="meta">
      <div class="title">Attack Path Viewer</div>
      <div class="subtitle" id="meta-line"></div>
    </div>
    <div id="controls">
      <button id="replay-btn">replay</button>
      <button id="reset-zoom-btn">reset</button>
    </div>
  </div>
  <div id="graph-container">
    <svg id="attack-graph"></svg>
    <div id="tooltip"></div>
    <div id="detail-panel">
      <button id="close-panel">×</button>
      <div id="panel-content"></div>
    </div>
  </div>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
  <script>
    const reportData = $REPORT_JSON;
    const graphData = $GRAPH_JSON;

    const metaLine = document.getElementById("meta-line");
    const objectiveMet = reportData.executive_summary?.objective_met ? "met" : "not met";
    const planner = reportData.execution_policy?.target || "unknown";
    metaLine.textContent = "objective " + objectiveMet + " · planner " + planner + " · steps " + reportData.steps_taken;

    const container = document.getElementById("graph-container");
    const bounds = container.getBoundingClientRect();
    const width = bounds.width || 1200;
    const height = bounds.height || 800;

    if (typeof d3 === "undefined") {
      container.insertAdjacentHTML("afterbegin", "<div style=\\"position:absolute;top:12px;left:12px;color:var(--accent2);font-family:var(--mono);font-size:12px;\\">D3 não carregou (offline ou CDN bloqueado). O grafo não pôde ser renderizado.</div>");
    } else {
      initGraph();
    }

    function initGraph() {
      const svg = d3.select("#attack-graph");
      svg.attr("viewBox", [0, 0, width, height])
        .attr("width", width)
        .attr("height", height);

      const defs = svg.append("defs");
    defs.append("filter")
      .attr("id", "glow")
      .append("feDropShadow")
      .attr("dx", 0)
      .attr("dy", 0)
      .attr("stdDeviation", 4)
      .attr("flood-color", "$ACCENT")
      .attr("flood-opacity", 0.35);

    const arrowTypes = [
      { id: "arrow-success", color: "$ACCENT" },
      { id: "arrow-rejected", color: "$ACCENT2" },
      { id: "arrow-assumed", color: "$AMBER" },
      { id: "arrow-default", color: "$BORDER" },
    ];
    defs.selectAll("marker")
      .data(arrowTypes)
      .join("marker")
      .attr("id", d => d.id)
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 14)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", d => d.color);

    const zoomLayer = svg.append("g");
    const tooltip = d3.select("#tooltip");
    const panel = document.getElementById("detail-panel");
    const panelContent = document.getElementById("panel-content");
    document.getElementById("close-panel").onclick = () => panel.classList.remove("open");

    const zoom = d3.zoom().scaleExtent([0.4, 2.5]).on("zoom", (event) => {
      zoomLayer.attr("transform", event.transform);
    });
    svg.call(zoom);
    document.getElementById("reset-zoom-btn").onclick = () => {
      svg.transition().duration(200).call(zoom.transform, d3.zoomIdentity);
    };

    computeDepths(graphData.nodes, graphData.links);
    const depthGroups = d3.group(graphData.nodes, d => d.depth ?? 0);
    const maxDepth = d3.max(graphData.nodes, d => d.depth ?? 0) || 0;
    const levelGap = Math.max(160, height / (maxDepth + 1));

    depthGroups.forEach((levelNodes, depth) => {
      const count = levelNodes.length || 1;
      levelNodes.forEach((node, idx) => {
        node.x = (idx + 1) * (width / (count + 1));
        node.y = (depth * levelGap) + 80;
      });
    });

    graphData.nodes.filter(n => n.type === "dead_end").forEach(node => {
      node.x += 60;
      node.y += 20;
    });

      const link = zoomLayer.append("g")
      .selectAll("line")
      .data(graphData.links)
      .join("line")
      .attr("x1", d => getNode(d.source).x)
      .attr("y1", d => getNode(d.source).y)
      .attr("x2", d => getNode(d.target).x)
      .attr("y2", d => getNode(d.target).y)
      .attr("stroke", d => linkColor(d.status, d.action))
      .attr("stroke-width", d => d.status === "success" ? 1.5 : 1)
      .attr("stroke-dasharray", d => d.status === "rejected" ? "4 3" : "0")
      .attr("marker-end", d => linkMarker(d.status, d.action));

      const node = zoomLayer.append("g")
      .selectAll("g")
      .data(graphData.nodes)
      .join("g")
      .attr("transform", d => "translate(" + d.x + "," + d.y + ")")
      .style("cursor", "pointer")
      .on("mouseover", (event, d) => showTooltip(event, d))
      .on("mouseout", hideTooltip)
      .on("click", (event, d) => showPanel(d));

    node.filter(d => d.type !== "identity").append("rect")
      .attr("stroke", d => nodeStroke(d.type))
      .attr("fill", d => nodeFill(d.type))
      .attr("stroke-width", d => d.type === "objective" ? 2 : 1)
      .attr("stroke-dasharray", d => d.type === "dead_end" ? "4 3" : "0")
      .attr("rx", 10)
      .attr("ry", 10)
      .attr("width", 180)
      .attr("height", 48)
      .attr("x", -90)
      .attr("y", -24)
      .attr("filter", d => d.type === "objective" ? "url(#glow)" : null);

    node.filter(d => d.type === "identity").append("ellipse")
      .attr("rx", 70)
      .attr("ry", 22)
      .attr("cx", 0)
      .attr("cy", 0)
      .attr("stroke", d => nodeStroke(d.type))
      .attr("fill", d => nodeFill(d.type))
      .attr("stroke-width", 1);

    node.append("text")
      .text(d => truncateLabel(d.label || d.name || d.id))
      .attr("text-anchor", "middle")
      .attr("dy", 4)
      .attr("fill", "$TEXT")
      .attr("font-family", "$MONO")
      .attr("font-size", 11);

      const replayBtn = document.getElementById("replay-btn");
    let replaying = false;
      replayBtn.onclick = () => {
      if (replaying) {
        replaying = false;
        replayBtn.textContent = "replay";
        return;
      }
      replaying = true;
      replayBtn.textContent = "pause";
      replay();
    };

      function replay() {
      node.attr("opacity", 0);
      link.attr("opacity", 0);
      let step = 0;
      const nodesByStep = groupBy(graphData.nodes, d => d.step || 0);
      const linksByStep = groupBy(graphData.links, d => d.step || 0);
      const maxStep = d3.max(graphData.nodes, d => d.step || 0) || 0;
      const timer = setInterval(() => {
        if (!replaying) {
          clearInterval(timer);
          return;
        }
        step += 1;
        const ns = nodesByStep.get(step) || [];
        const ls = linksByStep.get(step) || [];
        const currentNodes = node.filter(d => ns.includes(d));
        currentNodes.transition().attr("opacity", 1);
        currentNodes.selectAll("rect, ellipse")
          .transition()
          .duration(150)
          .attr("stroke", "$ACCENT")
          .transition()
          .duration(200)
          .attr("stroke", d => nodeStroke(d.type));
        link.filter(d => ls.includes(d)).transition().attr("opacity", 1);
        if (step >= maxStep) {
          replaying = false;
          replayBtn.textContent = "replay";
          clearInterval(timer);
        }
      }, 400);
    }

      function getNode(id) {
      return graphData.nodes.find(n => n.id === id) || {x:0, y:0};
    }

      function nodeFill(type) {
      if (type === "objective") return "#2d3c1b";
      if (type === "dead_end") return "rgba(240,74,42,0.15)";
      if (type === "identity") return "$SURFACE";
      return "$SURFACE";
    }

      function nodeStroke(type) {
      if (type === "objective") return "$ACCENT";
      if (type === "dead_end") return "$ACCENT2";
      if (type === "identity") return "$ACCENT3";
      return "$BORDER";
    }

      function linkColor(status, action) {
      if (status === "rejected") return "$ACCENT2";
      if (action === "assume_role") return "$AMBER";
      if (status === "success") return "$ACCENT";
      return "$BORDER";
    }

      function linkMarker(status, action) {
      if (status === "rejected") return "url(#arrow-rejected)";
      if (action === "assume_role") return "url(#arrow-assumed)";
      if (status === "success") return "url(#arrow-success)";
      return "url(#arrow-default)";
    }

      function showTooltip(event, d) {
      let html = "<div><strong>" + d.type + "</strong></div>";
      html += "<div>" + (d.name || d.label || d.id) + "</div>";
      if (d.mitre_id) {
        html += "<div>MITRE: " + d.mitre_id + "</div>";
      }
      if (d.action) {
        html += "<div>action: " + d.action + "</div>";
      }
      tooltip.style("display", "block")
        .style("left", (event.offsetX + 12) + "px")
        .style("top", (event.offsetY + 12) + "px")
        .html(html);
    }

      function hideTooltip() {
      tooltip.style("display", "none");
    }

      function showPanel(d) {
      const content = [
        "name: " + (d.name || d.label || d.id),
        "type: " + d.type,
        d.step ? "step: " + d.step : null,
        d.action ? "action: " + d.action : null,
        d.reason ? "reason: " + d.reason : null,
        d.mitre_id ? "mitre: " + d.mitre_id : null,
        d.status ? "status: " + d.status : null,
      ].filter(Boolean).join("\\n");
      panelContent.textContent = content;
      panel.classList.add("open");
    }

      function truncateLabel(label, maxChars = 24) {
      if (!label) return "";
      if (label.length <= maxChars) return label;
      if (label.startsWith("arn:")) {
        const parts = label.split(":");
        return "..." + parts.slice(-2).join(":");
      }
      return label.substring(0, maxChars) + "...";
      }

      function computeDepths(nodes, links) {
      const incoming = new Map();
      const adjacency = new Map();
      nodes.forEach(n => {
        incoming.set(n.id, 0);
        adjacency.set(n.id, []);
      });
      links.forEach(l => {
        if (adjacency.has(l.source) && adjacency.has(l.target)) {
          adjacency.get(l.source).push(l.target);
          incoming.set(l.target, (incoming.get(l.target) || 0) + 1);
        }
      });
      const root = nodes.find(n => n.type === "identity" && !(incoming.get(n.id) > 0))
        || nodes.find(n => (incoming.get(n.id) || 0) === 0);
      if (!root) return;
      const queue = [{ id: root.id, depth: 0 }];
      const depthMap = {};
      while (queue.length > 0) {
        const { id, depth } = queue.shift();
        if (depthMap[id] !== undefined) continue;
        depthMap[id] = depth;
        (adjacency.get(id) || []).forEach(tgt => queue.push({ id: tgt, depth: depth + 1 }));
      }
      nodes.forEach(n => {
        n.depth = depthMap[n.id] ?? 0;
      });
      }

      function groupBy(list, keyFn) {
      const map = new Map();
      list.forEach(item => {
        const key = keyFn(item);
        if (!map.has(key)) map.set(key, []);
        map.get(key).push(item);
      });
      return map;
      }
    }
  </script>
</body>
</html>"""
    )

    return template.substitute(
        BG=COLORS["bg"],
        SURFACE=COLORS["surface"],
        BORDER=COLORS["border"],
        TEXT=COLORS["text"],
        MUTED=COLORS["muted"],
        ACCENT=COLORS["accent"],
        ACCENT2=COLORS["accent2"],
        ACCENT3=COLORS["accent3"],
        AMBER=COLORS["amber"],
        MONO=COLORS["mono_font"],
        SANS=COLORS["sans_font"],
        REPORT_JSON=report_json,
        GRAPH_JSON=graph_json,
    )
