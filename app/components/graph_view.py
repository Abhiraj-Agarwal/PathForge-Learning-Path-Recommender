"""Roadmap graph component: left-to-right DAG grouped into milestone clusters."""
import graphviz

SKILL_COLORS = {
    "mastered": "#c8efc8",      # green
    "in_progress": "#fff3b0",   # amber
    "upcoming": "#e2e2e2",      # grey
}


def build_roadmap_graph(path: dict) -> graphviz.Digraph:
    """Build a graphviz Digraph for a ``{milestones, edges, role}`` dict."""
    graph = graphviz.Digraph(graph_attr={"rankdir": "LR", "ranksep": "1.2"})
    graph.attr("graph", fontname="Helvetica")
    graph.attr("node", shape="box", fontname="Helvetica", style="filled")
    graph.attr("edge", color="darkgrey", arrowsize="0.8")

    for milestone_id, steps in path["milestones"].items():
        milestone_label = (steps[0].get("milestone", f"Milestone {milestone_id}")
                           if steps else f"Milestone {milestone_id}")
        with graph.subgraph(name=f"cluster_{milestone_id}") as cluster:
            cluster.attr(
                label=milestone_label,
                style="rounded,dashed",
                color="grey",
                fontsize="11",
            )
            for step in steps:
                cluster.node(
                    step["skill_id"],
                    step["name"],
                    fillcolor=SKILL_COLORS.get(step["status"], SKILL_COLORS["upcoming"]),
                )

    for source, target in path["edges"]:
        graph.edge(source, target)
    return graph