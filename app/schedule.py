"""Turns a computed LearningPath into a day-by-day study schedule.

Still no invented facts: the hour estimate per skill comes from the top
ranked course's real ``duration_hours`` when one was matched, falling back to
the planner's own flat estimate otherwise. This module only decides *when*
those hours land relative to the learner's stated weekly budget -- the
ordering itself was already decided by ``core/planner.py``.

A full 7-day calendar week is shown (Monday-Sunday), with weekends left as
rest/catch-up since the hour budget is spread across the 5 weekdays -- this
gives learners an honest, complete week view rather than just weekday slots.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from schemas.models import Course

from core.planner import DEFAULT_HOURS_PER_SKILL

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
STUDY_DAYS = 5  # first N day names get the weekly hour budget; the rest are rest days

# A skill with few or no prerequisites of its own (Git, command line,
# programming basics) is structurally foundational -- quick to get moving on,
# regardless of how often it's mentioned in job postings. It gets a lighter,
# capped time budget instead of a full course's real length, so pacing
# doesn't sink a whole week into a warm-up skill. The cap reuses the
# planner's own general per-skill estimate (core/planner.py) rather than a
# new invented number. Deeper skills (real prerequisite chains behind them --
# actual complexity) keep their real course length.
PREREQ_HOURS_CAP = DEFAULT_HOURS_PER_SKILL
FOUNDATIONAL_ANCESTOR_MAX = 1


@dataclass
class DayEntry:
    day: str
    entries: list[tuple[str, float, Course | None]] = field(default_factory=list)  # (skill_id, hours, course)


@dataclass
class WeekPlan:
    week: int
    days: list[DayEntry]


def _skill_hours(path, graph, courses_by_id) -> list[list]:
    """Flat [skill_id, hours_remaining, course] list in planner order, using
    real course length (and carrying the course itself, for linking) when a
    resource was matched -- capped for structurally foundational skills so
    pacing stays realistic, regardless of how in-demand they are."""
    items = []
    for milestone in path.milestones:
        for planned in milestone.skills:
            course = courses_by_id.get(planned.course_ids[0]) if planned.course_ids else None
            raw_hours = course.duration_hours if course is not None else DEFAULT_HOURS_PER_SKILL
            is_foundational = len(graph.ancestors_of(planned.skill_id)) <= FOUNDATIONAL_ANCESTOR_MAX
            hours = min(raw_hours, PREREQ_HOURS_CAP) if is_foundational else raw_hours
            items.append([planned.skill_id, float(hours), course])
    return items


def build_day_schedule(path, graph, courses_by_id, hours_per_week: float,
                       max_weeks: int = 1) -> tuple[list[WeekPlan], bool]:
    """Distributes each skill's hours across a 7-day week, in planner order.

    Returns ``(weeks, is_complete)`` where ``is_complete`` is True when every
    skill in the path fit inside ``max_weeks`` (so the caller can say
    "...and N more skills after this" instead of implying the plan stops).
    """
    remaining = _skill_hours(path, graph, courses_by_id)
    hours_per_day = (hours_per_week / STUDY_DAYS) if hours_per_week else 0.0

    weeks: list[WeekPlan] = []
    item_idx = 0
    for week_num in range(1, max_weeks + 1):
        if item_idx >= len(remaining) or hours_per_day <= 0:
            break
        days: list[DayEntry] = []
        for slot, day_name in enumerate(DAY_NAMES):
            day = DayEntry(day=day_name)
            budget = hours_per_day if slot < STUDY_DAYS else 0.0
            while budget > 1e-6 and item_idx < len(remaining):
                skill_id, hours_left, course = remaining[item_idx]
                take = min(budget, hours_left)
                if take > 1e-6:
                    day.entries.append((skill_id, take, course))
                remaining[item_idx][1] -= take
                budget -= take
                if remaining[item_idx][1] <= 1e-6:
                    item_idx += 1
            days.append(day)
        weeks.append(WeekPlan(week=week_num, days=days))
        if item_idx >= len(remaining):
            break

    return weeks, item_idx >= len(remaining)


def format_schedule_markdown(weeks: list[WeekPlan], graph, is_complete: bool,
                             total_skills: int, hours_per_week: float) -> str:
    """Renders the week/day structure as compact, merged markdown with course
    links -- runs of consecutive identical days collapse into one line
    ("Mon-Wed: ...")."""
    if not weeks:
        return "_Nothing left to schedule -- you're already there on the skills that matter._"

    def _entry_key(entries):
        return [(sid, round(hrs, 3)) for sid, hrs, _ in entries]

    lines = [f"**Pace: ~{hours_per_week:.0f} hrs/week across the 5 weekdays**\n"]
    for week in weeks:
        lines.append(f"**Week {week.week}**")
        run_start = 0
        for i in range(1, len(week.days) + 1):
            same = i < len(week.days) and _entry_key(week.days[i].entries) == _entry_key(week.days[run_start].entries)
            if same:
                continue
            span = week.days[run_start:i]
            entries = span[0].entries
            day_label = span[0].day if len(span) == 1 else f"{span[0].day}-{span[-1].day}"
            if not entries:
                lines.append(f"- **{day_label}**: _rest / catch-up_")
            else:
                parts = []
                for sid, hrs, course in entries:
                    name = graph.get(sid).name
                    if course is not None:
                        parts.append(f"[{name}]({course.url}) ({hrs:.1f}h)")
                    else:
                        parts.append(f"{name} ({hrs:.1f}h)")
                lines.append(f"- **{day_label}**: {', '.join(parts)}")
            run_start = i
        lines.append("")

    if not is_complete:
        shown = len({sid for w in weeks for d in w.days for sid, _, _ in d.entries})
        remaining_count = max(total_skills - shown, 0)
        if remaining_count:
            lines.append(
                f"_...and **{remaining_count} more skills** after this. Open the **🗺️ Roadmap** "
                "tab and click any node to see its relevance score, impact score and course "
                "links._"
            )

    return "\n".join(lines)
