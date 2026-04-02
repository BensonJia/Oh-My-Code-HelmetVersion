# tests/skills/test_loader.py
import pytest
from pathlib import Path
from ohmycode.skills.loader import SkillInfo, parse_frontmatter, scan_skills, load_skill

def test_parse_frontmatter_basic():
    text = "---\nname: my-skill\ndescription: A test skill\n---\n\n# Hello\n\nBody content."
    meta, body = parse_frontmatter(text)
    assert meta["name"] == "my-skill"
    assert meta["description"] == "A test skill"
    assert "# Hello" in body
    assert "Body content." in body

def test_parse_frontmatter_no_frontmatter():
    text = "# Just a markdown file\n\nNo frontmatter here."
    meta, body = parse_frontmatter(text)
    assert meta == {}
    assert "# Just a markdown file" in body

def test_parse_frontmatter_empty_description():
    text = "---\nname: empty\n---\n\nBody."
    meta, body = parse_frontmatter(text)
    assert meta["name"] == "empty"
    assert "description" not in meta

def test_scan_skills_finds_skills(tmp_path):
    skill_dir = tmp_path / ".ohmycode" / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: test-skill\ndescription: A test\n---\n\nDo something.")
    skills = scan_skills(cwd=str(tmp_path))
    assert "test-skill" in skills
    assert skills["test-skill"].description == "A test"

def test_scan_skills_priority(tmp_path):
    for sub in (".ohmycode/skills/dupe", ".claude/skills/dupe"):
        (tmp_path / sub).mkdir(parents=True)
    (tmp_path / ".ohmycode" / "skills" / "dupe" / "SKILL.md").write_text("---\ndescription: from ohmycode\n---\nA")
    (tmp_path / ".claude" / "skills" / "dupe" / "SKILL.md").write_text("---\ndescription: from claude\n---\nB")
    skills = scan_skills(cwd=str(tmp_path))
    assert skills["dupe"].description == "from ohmycode"

def test_scan_skills_reads_claude_and_agents(tmp_path):
    for sub, desc in [(".claude/skills/s1", "claude"), (".agents/skills/s2", "agents")]:
        (tmp_path / sub).mkdir(parents=True)
        (tmp_path / sub / "SKILL.md").write_text(f"---\ndescription: {desc}\n---\nBody")
    skills = scan_skills(cwd=str(tmp_path))
    assert "s1" in skills
    assert "s2" in skills


def test_scan_skills_nested_group_folder(tmp_path):
    """e.g. .claude/skills/superpowers/brainstorming/SKILL.md"""
    nested = tmp_path / ".claude" / "skills" / "superpowers" / "brainstorming"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text("---\ndescription: nested skill\n---\nBody")
    skills = scan_skills(cwd=str(tmp_path))
    assert "brainstorming" in skills
    assert skills["brainstorming"].description == "nested skill"
    assert "superpowers" not in skills

def test_load_skill_replaces_arguments(tmp_path):
    skill_dir = tmp_path / "sk"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: sk\ndescription: test\n---\n\nCreate $ARGUMENTS now.")
    info = SkillInfo(name="sk", description="test", path=skill_dir / "SKILL.md", base_dir=str(skill_dir), source=".ohmycode/skills/")
    content = load_skill(info, arguments="MyTool")
    assert "Create MyTool now." in content
    assert "$ARGUMENTS" not in content

def test_load_skill_adds_base_dir(tmp_path):
    skill_dir = tmp_path / "sk"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: sk\ndescription: test\n---\n\nBody.")
    info = SkillInfo(name="sk", description="test", path=skill_dir / "SKILL.md", base_dir=str(skill_dir), source=".ohmycode/skills/")
    content = load_skill(info)
    assert content.startswith(f"Base directory for this skill: {skill_dir}")

def test_load_skill_no_arguments_placeholder(tmp_path):
    skill_dir = tmp_path / "sk"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: sk\ndescription: test\n---\n\nNo placeholder here.")
    info = SkillInfo(name="sk", description="test", path=skill_dir / "SKILL.md", base_dir=str(skill_dir), source=".ohmycode/skills/")
    content = load_skill(info, arguments="extra args")
    assert "extra args" in content
