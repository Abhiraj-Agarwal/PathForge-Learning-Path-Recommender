"""Learning resource card component: title, 'Why this?' and 👍/👎 feedback."""
import streamlit as st

try:
    from api_client import post_feedback
except Exception:  # api_client may not be importable in exotic layouts
    def post_feedback(_payload):
        return {"status": "unavailable"}


TYPE_ICONS = {"course": "🎓", "project": "🛠️", "assessment": "📝", "article": "📰", "video": "🎬"}


def render_resource_cards(resources, context: str = ""):
    """Render one card per resource with a reason and thumbs feedback buttons."""
    for res in resources:
        with st.container(border=True):
            col_main, col_btn = st.columns([4, 1], vertical_alignment="center")

            with col_main:
                res_type = res.get("type", "course")
                st.markdown(f"**[{res['title']}]({res['url']})**")
                badge_cols = st.columns(3 if res.get("rating") else 2)
                badge_cols[0].badge(res["provider"], icon="🏫", color="blue")
                badge_cols[1].badge(res_type.title(), icon=TYPE_ICONS.get(res_type, "📘"), color="violet")
                if res.get("rating"):
                    badge_cols[2].badge(f"{res['rating']:.1f}★", color="orange")
                st.caption(f"💡 *Why this?* {res.get('justification', res.get('reason', ''))}")

            with col_btn:
                c1, c2 = st.columns(2)
                up_key = f"up_{context}_{res['id']}"
                down_key = f"down_{context}_{res['id']}"

                def _log(kind):
                    payload = {
                        "resource_id": res["id"],
                        "reaction": kind,
                        "skill": res.get("skill_id") or res.get("skill"),
                    }
                    st.session_state.get("feedback", []).append({"resource_id": res["id"], "reaction": kind})
                    post_feedback(payload)

                with c1:
                    if st.button("👍", key=up_key, help="Useful", width="stretch"):
                        _log("up")
                        st.toast(f"👍 Feedback logged for {res['title']}")
                with c2:
                    if st.button("👎", key=down_key, help="Not useful", width="stretch"):
                        _log("down")
                        st.toast(f"👎 Feedback logged for {res['title']}")