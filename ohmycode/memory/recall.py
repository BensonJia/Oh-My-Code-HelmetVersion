"""Keyword-based memory recall engine (Phase 3).

Selects relevant category branches from the B+-Tree without any LLM API call.
Uses keyword overlap between the user query and category _SUMMARY.md content
to decide which branches to load — analogous to B+-Tree key comparison at
internal nodes.
"""

from __future__ import annotations

import re
from typing import List

from ohmycode.memory.memory import BTreeMemoryStore, VALID_CATEGORIES

# Keywords that signal interest in each category
_CATEGORY_SIGNALS: dict[str, list[str]] = {
    "user": [
        "my background", "my experience", "my role", "who am i", "my preference",
        "about me", "my profile", "my expertise", "my skill", "my team",
        "i am", "i'm a", "i work", "i prefer",
    ],
    "feedback": [
        "rule", "convention", "test", "testing", "style", "format", "lint",
        "commit", "pr", "pull request", "review", "mock", "don't", "do not",
        "stop", "avoid", "prefer", "workflow", "guideline", "policy",
        "npm", "bun", "package", "toolchain",
    ],
    "project": [
        "deadline", "timeline", "freeze", "release", "sprint", "milestone",
        "rewrite", "migration", "incident", "auth", "compliance", "legal",
        "initiative", "goal", "plan", "progress", "status", "block",
    ],
    "reference": [
        "dashboard", "grafana", "linear", "jira", "slack", "link", "url",
        "monitor", "oncall", "alert", "external", "api", "doc", "portal",
        "where is", "where can i find", "where do",
    ],
}

MAX_SELECTED_CATEGORIES = 3


def _tokenize(text: str) -> set[str]:
    """Split text into lowercase word tokens."""
    return set(re.findall(r'[a-z]+', text.lower()))


class RecallEngine:
    """Selects relevant memory categories via keyword matching, then assembles context."""

    def __init__(self, store: BTreeMemoryStore):
        self.store = store

    def select_categories(self, query: str) -> List[str]:
        """Score each category by keyword overlap and return the top matches."""
        if not query.strip():
            return []

        query_lower = query.lower()
        query_tokens = _tokenize(query)

        scores: dict[str, float] = {}
        for cat in VALID_CATEGORIES:
            score = 0.0

            # Signal-based scoring: check if query contains category-specific phrases
            for signal in _CATEGORY_SIGNALS.get(cat, []):
                if signal in query_lower:
                    score += 2.0
                signal_tokens = _tokenize(signal)
                overlap = query_tokens & signal_tokens
                if overlap:
                    score += len(overlap) * 0.5

            # Summary-based scoring: check overlap with actual memory names/content
            summary = self.store.get_category_summary(cat)
            if summary:
                summary_tokens = _tokenize(summary)
                overlap = query_tokens & summary_tokens
                # Filter out very common words
                stop_words = {"the", "a", "an", "is", "are", "was", "were", "do", "does",
                              "what", "how", "when", "where", "we", "i", "my", "our",
                              "have", "has", "had", "to", "for", "in", "on", "at", "of",
                              "and", "or", "not", "no", "with", "about", "this", "that"}
                meaningful_overlap = overlap - stop_words
                score += len(meaningful_overlap) * 1.0

            if score > 0:
                scores[cat] = score

        ranked = sorted(scores.keys(), key=lambda c: scores[c], reverse=True)
        return ranked[:MAX_SELECTED_CATEGORIES]

    def recall(self, query: str) -> str:
        """Assemble memory context: root index + relevant category summaries."""
        parts = [self.store.get_root_index()]

        selected = self.select_categories(query)
        for cat in selected:
            summary = self.store.get_category_summary(cat)
            if summary:
                parts.append(summary)

        return "\n\n".join(parts)
