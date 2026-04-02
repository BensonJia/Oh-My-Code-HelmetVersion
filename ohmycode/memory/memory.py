"""B+-Tree hierarchical memory system.

Three-level storage inspired by B+-Tree indexing:
  L0 (root)     — INDEX.md: compact per-category summary, always in system prompt
  L1 (internal) — _SUMMARY.md per category: entry list with one-line descriptions
  L2 (leaf)     — individual .md files with frontmatter + full content
"""

from __future__ import annotations

import hashlib
import os
import random
import re
import string
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List

MAX_INDEX_LINES = 30
MAX_INDEX_BYTES = 4096
VALID_CATEGORIES = ("user", "feedback", "project", "reference")


def _sanitize_slug(path_str: str) -> str:
    """Convert an absolute path to a filesystem-safe slug."""
    return hashlib.sha256(path_str.encode()).hexdigest()[:16]


def _find_git_root(cwd: str) -> str | None:
    """Find git repo root from cwd, or None if not in a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


def get_project_memory_dir(cwd: str) -> str:
    """Return per-project memory directory path. Uses git root if available, else cwd."""
    root = _find_git_root(cwd) or os.path.abspath(cwd)
    slug = _sanitize_slug(root)
    return str(Path.home() / ".ohmycode" / "projects" / slug / "memory")


def _parse_frontmatter_meta(content: str) -> tuple[str, str]:
    """Extract name and type from frontmatter block."""
    name = "unknown"
    mem_type = "general"
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            frontmatter = content[3:end]
            for line in frontmatter.splitlines():
                if line.startswith("name:"):
                    name = line.split(":", 1)[1].strip()
                elif line.startswith("type:"):
                    mem_type = line.split(":", 1)[1].strip()
    return name, mem_type


class BTreeMemoryStore:
    """Three-level B+-Tree-inspired memory store."""

    def __init__(self, memory_dir: Path | str):
        self.root = Path(memory_dir)
        self.index_path = self.root / "INDEX.md"

    def ensure_tree(self) -> None:
        """Create the directory structure: root + category dirs + empty INDEX.md."""
        self.root.mkdir(parents=True, exist_ok=True)
        for cat in VALID_CATEGORIES:
            (self.root / cat).mkdir(exist_ok=True)
        if not self.index_path.exists():
            self._rebuild_root_index()

    # ------------------------------------------------------------------
    # L2 leaf operations
    # ------------------------------------------------------------------

    def save(self, name: str, category: str, content: str) -> str:
        """Write a leaf .md file, update _SUMMARY.md and INDEX.md. Returns filename."""
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category '{category}'. Must be one of: {VALID_CATEGORIES}")

        ts = datetime.now().strftime("%Y%m%d%H%M%S%f")[:17]  # YYYYMMDDHHMMSSmmm
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        safe_name = re.sub(r"[^\w\-]", "_", name)[:40]
        filename = f"{ts}_{suffix}_{safe_name}.md"

        cat_dir = self.root / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        leaf_path = cat_dir / filename

        frontmatter = (
            f"---\n"
            f"name: {name}\n"
            f"type: {category}\n"
            f"created: {ts}\n"
            f"---\n\n"
        )
        leaf_path.write_text(frontmatter + content, encoding="utf-8")

        self._rebuild_category_summary(category)
        self._rebuild_root_index()
        return filename

    def delete(self, category: str, filename: str) -> bool:
        """Remove a leaf file and update summary/index. Returns True if deleted."""
        leaf_path = self.root / category / filename
        if not leaf_path.exists():
            return False
        leaf_path.unlink()
        self._rebuild_category_summary(category)
        self._rebuild_root_index()
        return True

    def read_leaf(self, category: str, filename: str) -> str:
        """Read full content of a leaf file."""
        leaf_path = self.root / category / filename
        return leaf_path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # L1 category summary operations
    # ------------------------------------------------------------------

    def list_category(self, category: str) -> List[dict]:
        """List all memories in a category. Returns list of {name, type, filename}."""
        cat_dir = self.root / category
        if not cat_dir.is_dir():
            return []
        results = []
        for md_file in sorted(cat_dir.glob("*.md")):
            if md_file.name.startswith("_"):
                continue
            try:
                raw = md_file.read_text(encoding="utf-8")
                name, mem_type = _parse_frontmatter_meta(raw)
                results.append({"name": name, "type": mem_type, "filename": md_file.name})
            except Exception:
                pass
        return results

    def get_category_summary(self, category: str) -> str:
        """Read the _SUMMARY.md for a category."""
        summary_path = self.root / category / "_SUMMARY.md"
        if summary_path.exists():
            return summary_path.read_text(encoding="utf-8")
        return ""

    def _rebuild_category_summary(self, category: str) -> None:
        """Regenerate _SUMMARY.md for one category from its leaf files."""
        entries = self.list_category(category)
        lines = [f"# {category} ({len(entries)} entries)\n"]
        for entry in entries:
            lines.append(f"- [{entry['name']}]({entry['filename']})")
        summary_path = self.root / category / "_SUMMARY.md"
        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ------------------------------------------------------------------
    # L0 root index operations
    # ------------------------------------------------------------------

    def list_all(self) -> List[dict]:
        """List all memories across all categories."""
        results = []
        for cat in VALID_CATEGORIES:
            results.extend(self.list_category(cat))
        return results

    def get_root_index(self) -> str:
        """Read INDEX.md content (for system prompt injection)."""
        if self.index_path.exists():
            content = self.index_path.read_text(encoding="utf-8")
            return self._enforce_caps(content)
        return "# Memory Index (empty)\n"

    def _rebuild_root_index(self) -> None:
        """Regenerate INDEX.md from all category summaries."""
        lines = ["# Memory Index"]
        total = 0
        for cat in VALID_CATEGORIES:
            entries = self.list_category(cat)
            count = len(entries)
            total += count
            if count == 0:
                continue
            names_preview = ", ".join(e["name"] for e in entries[:5])
            if count > 5:
                names_preview += f" (+{count - 5} more)"
            lines.append(f"- {cat} ({count}): {names_preview}")

        if total == 0:
            lines.append("(no memories yet)")

        content = "\n".join(lines) + "\n"
        content = self._enforce_caps(content)
        self.index_path.write_text(content, encoding="utf-8")

    @staticmethod
    def _enforce_caps(content: str) -> str:
        """Truncate index to stay within line and byte caps."""
        content_lines = content.strip().splitlines()
        if len(content_lines) > MAX_INDEX_LINES:
            content_lines = content_lines[:MAX_INDEX_LINES]
            content_lines.append("(truncated — too many entries)")
        result = "\n".join(content_lines) + "\n"
        if len(result.encode("utf-8")) > MAX_INDEX_BYTES:
            while len(result.encode("utf-8")) > MAX_INDEX_BYTES and content_lines:
                content_lines.pop()
                result = "\n".join(content_lines) + "\n(truncated — size limit)\n"
        return result


# ---- Legacy compatibility wrappers ----
# These wrap the old global-dir API so existing code doesn't break immediately.

MEMORY_DIR = Path.home() / ".ohmycode" / "memory"
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"


def ensure_memory_dir() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def load_memory_index() -> str:
    ensure_memory_dir()
    if MEMORY_INDEX.exists():
        return MEMORY_INDEX.read_text(encoding="utf-8")
    return ""


def save_memory(name: str, memory_type: str, content: str) -> str:
    ensure_memory_dir()
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")[:17]
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    safe_name = re.sub(r"[^\w\-]", "_", name)[:40]
    filename = f"{ts}_{suffix}_{safe_name}.md"
    filepath = MEMORY_DIR / filename
    frontmatter = f"---\nname: {name}\ntype: {memory_type}\ncreated: {ts}\n---\n\n"
    filepath.write_text(frontmatter + content, encoding="utf-8")
    MEMORY_INDEX.write_text(_build_index(), encoding="utf-8")
    return filename


def _build_index() -> str:
    lines = ["# OhMyCode Memory Index\n"]
    for md_file in sorted(MEMORY_DIR.glob("*.md")):
        if md_file.name == "MEMORY.md":
            continue
        try:
            raw = md_file.read_text(encoding="utf-8")
            name, mem_type = _parse_frontmatter_meta(raw)
            lines.append(f"- [{name}]({md_file.name}) type={mem_type}\n")
        except Exception:
            pass
    return "".join(lines)


def delete_memory(filename: str) -> bool:
    ensure_memory_dir()
    filepath = MEMORY_DIR / filename
    if not filepath.exists():
        return False
    filepath.unlink()
    MEMORY_INDEX.write_text(_build_index(), encoding="utf-8")
    return True


def list_memories() -> List[dict]:
    ensure_memory_dir()
    results = []
    for md_file in sorted(MEMORY_DIR.glob("*.md")):
        if md_file.name == "MEMORY.md":
            continue
        try:
            raw = md_file.read_text(encoding="utf-8")
            name, mem_type = _parse_frontmatter_meta(raw)
            results.append({"name": name, "type": mem_type, "filename": md_file.name})
        except Exception:
            pass
    return results


def filter_messages_for_extraction(messages: list) -> list:
    """Filter messages to only user/assistant with non-empty text content."""
    filtered = []
    for m in messages:
        role = getattr(m, 'role', None)
        if role not in ('user', 'assistant'):
            continue
        content = getattr(m, 'content', '') or ''
        if not content.strip():
            continue
        # Skip ToolResultMessage even if it has role='user'
        cls_name = type(m).__name__
        if 'ToolResult' in cls_name:
            continue
        filtered.append(m)
    return filtered


def parse_extraction_response(raw_text: str) -> List[dict]:
    """Robustly parse LLM extraction output into memory dicts.

    Tries in order: JSON array → JSON lines → regex extraction.
    Each dict must have name, type, and content keys.
    """
    import json

    required_keys = {"name", "type", "content"}

    def _is_valid(obj: dict) -> bool:
        return isinstance(obj, dict) and required_keys.issubset(obj.keys())

    # Strip markdown fences
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    # Try 1: parse as JSON array
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return [obj for obj in parsed if _is_valid(obj)]
    except (json.JSONDecodeError, ValueError):
        pass

    # Try 2: line-by-line JSON objects
    results = []
    for line in cleaned.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                obj = json.loads(line)
                if _is_valid(obj):
                    results.append(obj)
            except json.JSONDecodeError:
                pass
    if results:
        return results

    # Try 3: regex extraction of JSON objects
    import re
    for match in re.finditer(r'\{[^{}]+\}', cleaned):
        try:
            obj = json.loads(match.group())
            if _is_valid(obj):
                results.append(obj)
        except json.JSONDecodeError:
            pass
    return results


async def extract_memories_from_conversation(
    messages: list,
    provider,
    model: str,
) -> List[dict]:
    """Use LLM to extract memorable facts from the conversation."""
    try:
        from ohmycode.core.messages import UserMessage

        filtered = filter_messages_for_extraction(messages)
        conversation_text = "\n".join(
            f"{getattr(m, 'role', 'user')}: {getattr(m, 'content', '')}"
            for m in filtered
        )
        if not conversation_text.strip():
            return []

        prompt = (
            "Analyze this conversation and extract key facts worth remembering. "
            "For each memory, output a JSON object on its own line with keys: "
            '"name" (short label), "type" (one of: user, feedback, project, reference), "content" (1-2 sentences). '
            "Output ONLY JSON lines, no other text.\n\n"
            f"{conversation_text}"
        )
        request = [UserMessage(content=prompt)]
        result = await provider.complete(
            messages=request,
            model=model,
            system_prompt="You are a helpful assistant that extracts memorable facts from conversations.",
            tools=[],
        )
        raw_text = result.content if hasattr(result, "content") else str(result)
        return parse_extraction_response(raw_text)
    except Exception:
        return []
