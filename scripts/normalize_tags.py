"""Normalise raw course tags onto canonical skill ids.

Reads data/courses.json and data/skills.json. For every course, maps each
entry in `skill_tags` to a canonical skill id (name / id / alias match) and
writes the result into a new `skill_ids` field. The raw `skill_tags` array is
kept for transparency.

Untagged or unmapped courses stay visible but are reported so they can be
hand-edited -- a course with no `skill_ids` is invisible to the planner.

Usage:
  python scripts/normalize_tags.py            # reads data/, writes data/
  python scripts/normalize_tags.py --out data --match loose
"""

import argparse
from pathlib import Path

import json


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def build_alias_table(skills):
    """Return {normalised token: skill_id} for every id, name and alias."""
    table = {}
    for skill in skills:
        candidates = [skill["id"], skill["name"]] + list(skill.get("aliases", []))
        for candidate in candidates:
            table.setdefault(_normalize(candidate), skill["id"])
    return table


def map_tags(tags, table, mode="exact"):
    """Map raw tags to canonical skill ids.

    mode="exact" matches normalised tokens exactly.
    mode="loose" additionally allows token-overlap matches
      (e.g. 'basic sql 101' -> sql_basics via its alias 'basic sql').
    """
    matched, unmatched = [], []
    for tag in tags:
        key = _normalize(tag)
        if key in table:
            matched.append(table[key])
            continue
        if mode == "loose":
            # try to find a known token that is contained in the raw tag
            hit = None
            for known, skill_id in table.items():
                if known in key:
                    hit = (skill_id, known)
            if hit is not None:
                matched.append(hit[0])
                continue
        unmatched.append(tag)
    # preserve order and drop duplicates
    return list(dict.fromkeys(matched)), unmatched


def main():
    parser = argparse.ArgumentParser(description="Normalise course tags to canonical skill ids")
    parser.add_argument("--data", default="data", help="data directory (default: data)")
    parser.add_argument("--match", default="exact", choices=["exact", "loose"])
    parser.add_argument("--write", action="store_true",
                        help="write normalised skill_ids back to courses.json (default: preview)")
    args = parser.parse_args()

    data_dir = Path(args.data).resolve()
    skills = json.loads((data_dir / "skills.json").read_text(encoding="utf-8"))
    courses = json.loads((data_dir / "courses.json").read_text(encoding="utf-8"))

    table = build_alias_table(skills)
    total_tags = 0
    for course in courses:
        tags = course.get("skill_tags", [])
        total_tags += len(tags)
        skill_ids, unmatched = map_tags(tags, table, mode=args.match)
        course["skill_ids"] = skill_ids
        if unmatched:
            print(f"  UNMAPPED {course['id']}: {unmatched}")

    mapped = sum(1 for c in courses if c["skill_ids"])
    print(f"{len(courses)} courses, {mapped} with >=1 mapped skill, "
          f"{total_tags} raw tags checked (mode={args.match})")

    if args.write:
        (data_dir / "courses.json").write_text(
            json.dumps(courses, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote skill_ids to {data_dir / 'courses.json'}")


if __name__ == "__main__":
    main()