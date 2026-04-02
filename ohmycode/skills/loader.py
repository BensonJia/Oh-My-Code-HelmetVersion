"""Skill loader: scan layered paths, parse frontmatter, load skill content."""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SkillInfo:
    name: str
    description: str
    path: Path
    base_dir: str
    source: str

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)

def parse_frontmatter(text: str) -> tuple[dict, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    body = text[m.end():]
    metadata: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            metadata[key.strip()] = value.strip()
    return metadata, body

def _register_skill(
    skill_dir: Path,
    map_key: str,
    source_label: str,
    skills: dict[str, SkillInfo],
) -> None:
    skill_file = skill_dir / "SKILL.md"
    if not skill_file.is_file() or map_key in skills:
        return
    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError:
        return
    meta, _ = parse_frontmatter(text)
    name = meta.get("name", map_key)
    description = meta.get("description", "")
    skills[map_key] = SkillInfo(
        name=name,
        description=description,
        path=skill_file.resolve(),
        base_dir=str(skill_dir.resolve()),
        source=source_label,
    )


def _scan_one_skills_root(base_dir: Path, source_label: str, skills: dict[str, SkillInfo]) -> None:
    """Flat dirs `<root>/<name>/SKILL.md` or one level of grouping `<root>/<group>/<name>/SKILL.md`."""
    for child in sorted(base_dir.iterdir()):
        if not child.is_dir():
            continue
        if (child / "SKILL.md").is_file():
            _register_skill(child, child.name, source_label, skills)
            continue
        for nested in sorted(child.iterdir()):
            if not nested.is_dir():
                continue
            _register_skill(nested, nested.name, source_label, skills)


def scan_skills(cwd: str = ".") -> dict[str, SkillInfo]:
    cwd_path = Path(cwd).resolve()
    home = Path.home()
    search_dirs = [
        (cwd_path / ".ohmycode" / "skills", ".ohmycode/skills/"),
        (cwd_path / ".claude" / "skills", ".claude/skills/"),
        (cwd_path / ".agents" / "skills", ".agents/skills/"),
        (home / ".ohmycode" / "skills", "~/.ohmycode/skills/"),
    ]
    skills: dict[str, SkillInfo] = {}
    for base_dir, source_label in search_dirs:
        if not base_dir.is_dir():
            continue
        _scan_one_skills_root(base_dir, source_label, skills)
    return skills

def load_skill(skill: SkillInfo, arguments: str = "") -> str:
    text = skill.path.read_text(encoding="utf-8")
    _, body = parse_frontmatter(text)
    body = body.strip()
    if arguments:
        if "$ARGUMENTS" in body:
            body = body.replace("$ARGUMENTS", arguments)
        else:
            body = body + "\n\n" + arguments
    return f"Base directory for this skill: {skill.base_dir}\n\n{body}"
