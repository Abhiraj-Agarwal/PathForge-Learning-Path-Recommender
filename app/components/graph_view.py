"""Roadmap graph component: left-to-right DAG grouped into milestone clusters."""
import graphviz

# fill / border pairs, keyed to the same status vocabulary as the dashboard badges
SKILL_COLORS = {
    "mastered": ("#c8efc8", "#0ca30c"),      # green tint / green border
    "in_progress": ("#ffe9b3", "#c98500"),   # amber tint / amber border
    "upcoming": ("#e7e6e2", "#898781"),      # grey tint / muted border
}

FONT = "system-ui, -apple-system, Segoe UI, Helvetica, sans-serif"


def build_roadmap_graph(path: dict) -> graphviz.Digraph:
    """Build a graphviz Digraph for a ``{milestones, edges, role}`` dict."""
    graph = graphviz.Digraph(graph_attr={"rankdir": "LR", "ranksep": "1.1", "bgcolor": "transparent"})
    graph.attr("graph", fontname=FONT)
    graph.attr("node", shape="box", style="filled,rounded", fontname=FONT,
               fontsize="11", margin="0.18,0.12", penwidth="1.4")
    graph.attr("edge", color="#b0aea6", arrowsize="0.7", penwidth="1.1")

    for milestone_id, steps in path["milestones"].items():
        milestone_label = (steps[0].get("milestone", f"Milestone {milestone_id}")
                           if steps else f"Milestone {milestone_id}")
        with graph.subgraph(name=f"cluster_{milestone_id}") as cluster:
            cluster.attr(
                label=milestone_label,
                style="rounded,dashed",
                color="#b0aea6",
                fontname=FONT,
                fontsize="11",
                fontcolor="#52514e",
            )
            for step in steps:
                fill, border = SKILL_COLORS.get(step["status"], SKILL_COLORS["upcoming"])
                cluster.node(
                    step["skill_id"],
                    step["name"],
                    fillcolor=fill,
                    color=border,
                    fontcolor="#0b0b0b",
                )

    for source, target in path["edges"]:
        graph.edge(source, target)
    return graph