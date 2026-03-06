"""Challenge engine — generates targeted coding exercises via LLM.

Creates practice challenges for skills in the "dead zone" (decaying
from lack of hands-on use) to help developers stay sharp. Responses
from the LLM are sanitised before JSON parsing to guard against
injection or malformed output.
"""

import json
import re
from pathlib import Path

from atrophy.exceptions import ProviderError
from atrophy.providers.base import BaseLLMProvider

# ── System prompt ───────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a senior software engineer running a 1:1 mentoring session.
Your mentee is a real developer — not a student. Generate a short, practical
coding exercise they can do in their actual project (not a toy example).

RULES:
- The task must reference real patterns from their codebase shown below
- Do NOT invent imaginary classes, models, or APIs not shown in the context
- The task should be doable without running the app (a standalone function or module)
- NO LeetCode. NO "implement a linked list". Real world only.
- If you cannot generate a contextually accurate challenge, set "fallback": true
  and generate a generic but honest exercise for the skill

Respond in JSON only. No markdown. No preamble.\
"""

# ── Required keys and their expected types ──────────────────────────

_REQUIRED_KEYS: dict[str, type] = {
    "title": str,
    "description": str,
    "skill_name": str,
    "difficulty": str,
    "estimated_minutes": int,
    "hints": list,
    "success_criteria": str,
    "fallback": bool,
}

# ── Difficulty tiers ────────────────────────────────────────────────

_DIFFICULTY_TIERS: list[tuple[str, int]] = [
    ("easy", 20),
    ("medium", 40),
    ("hard", 60),
]

# Max string field length to prevent LLM flooding
_MAX_FIELD_LEN = 2000


# ── ChallengeEngine ────────────────────────────────────────────────


class ChallengeEngine:
    """Generates personalised coding challenges for decaying skills.

    Uses an LLM provider to create challenges tailored to the
    developer's tech stack and actual codebase patterns. Each challenge
    targets a specific dead-zone skill with appropriate difficulty.
    """

    def __init__(self, provider: BaseLLMProvider) -> None:
        """Initialise with an LLM provider.

        Args:
            provider: Any concrete ``BaseLLMProvider`` implementation
                (OpenAI, Anthropic, or Ollama).
        """
        self.provider = provider

    # ── Public API ──────────────────────────────────────────────────

    async def generate_challenges(
        self,
        dead_zones: list[str],
        language: str,
        repo_path: Path,
        commits: list[dict],
    ) -> list[dict]:
        from atrophy.core.context_builder import ContextBuilder
        cb = ContextBuilder(repo_path)
        
        # Select up to 3 dead zones
        selected = dead_zones[:3]
        if not selected:
            return []

        challenges: list[dict] = []
        for idx, skill_name in enumerate(selected):
            difficulty, estimated_minutes = _DIFFICULTY_TIERS[
                min(idx, len(_DIFFICULTY_TIERS) - 1)
            ]
            context = cb.build_challenge_context(skill_name, commits, language)
            
            user_prompt = self._build_user_prompt(
                skill_name=skill_name,
                difficulty=difficulty,
                estimated_minutes=estimated_minutes,
                context=context,
            )

            challenge = await self._call_and_parse(
                user_prompt=user_prompt,
                skill_name=skill_name,
                difficulty=difficulty,
                estimated_minutes=estimated_minutes,
            )
            challenges.append(challenge)

        return challenges



    # ── Private helpers ─────────────────────────────────────────────

    @staticmethod
    def _build_user_prompt(
        skill_name: str,
        difficulty: str,
        estimated_minutes: int,
        context: str,
    ) -> str:
        return (
            f"Skill to practice: {skill_name}\n"
            f"Difficulty: {difficulty} (~{estimated_minutes} minutes)\n"
            f"Developer context:\n"
            f"{context}\n"
            f"\n"
            f"Generate:\n"
            f"{{\n"
            f'  "title": "max 8 words",\n'
            f'  "description": "2-3 sentences. Must reference something from the context above.",\n'
            f'  "skill_name": "{skill_name}",\n'
            f'  "difficulty": "{difficulty}",\n'
            f'  "estimated_minutes": {estimated_minutes},\n'
            f'  "hints": ["hint using their actual stack", "second hint"],\n'
            f'  "success_criteria": "one sentence they can verify",\n'
            f'  "fallback": false\n'
            f"}}"
        )

    async def _call_and_parse(
        self,
        user_prompt: str,
        skill_name: str,
        difficulty: str,
        estimated_minutes: int,
    ) -> dict:
        """Call the LLM and parse/validate the response.

        SECURITY: Sanitises the LLM response before JSON parsing:
        - Strips markdown code fences (```json … ```)
        - Validates all required keys exist
        - Validates types (strings are str, minutes is int 5–120)
        - Truncates string fields longer than 2000 chars
        - Returns a hardcoded fallback challenge on any failure

        Args:
            user_prompt: The formatted user prompt.
            skill_name: Target skill (for fallback).
            difficulty: Target difficulty (for fallback).
            estimated_minutes: Target minutes (for fallback).

        Returns:
            A validated challenge dict.
        """
        try:
            raw = await self.provider.complete(
                system=SYSTEM_PROMPT,
                user=user_prompt,
                max_tokens=800,
            )
            cleaned = _strip_markdown_fences(raw)
            parsed = json.loads(cleaned)
            parsed = _validate_challenge(parsed)
            
            # Check for fallback
            if parsed.get("fallback", False):
                return _fallback_challenge(skill_name, difficulty, estimated_minutes)
            
            # Additional check: does description reference anything from context?
            # Find context words and check if any exist in description over length 4
            import re
            context_words = set(re.findall(r'\b[a-zA-Z_]{5,}\b', user_prompt.lower()))
            desc_words = set(re.findall(r'\b[a-zA-Z_]{5,}\b', parsed["description"].lower()))
            if not (context_words & desc_words):
                # Probably generic, use fallback
                return _fallback_challenge(skill_name, difficulty, estimated_minutes)
            
            return parsed

        except (ProviderError, json.JSONDecodeError, KeyError,
                TypeError, ValueError):
            # Return a safe fallback — never crash
            return _fallback_challenge(
                skill_name, difficulty, estimated_minutes
            )

        except Exception:
            # Catch-all for truly unexpected errors
            return _fallback_challenge(
                skill_name, difficulty, estimated_minutes
            )

    @staticmethod
    def _strip_paths(line: str) -> str:
        """Replace full file paths with basenames only.

        SECURITY: Prevents leaking directory structure to the LLM.

        Args:
            line: A line of code that may contain file paths.

        Returns:
            Line with any obvious file paths replaced by basenames.
        """
        # Match common path patterns: /foo/bar/baz.py or C:\foo\bar.py
        def _replace(match: re.Match) -> str:
            return Path(match.group()).name

        # Unix-style paths
        line = re.sub(r"(?<=[\"' (,=])(/[\w./-]+\.\w+)", _replace, line)
        # Windows-style paths
        line = re.sub(
            r"(?<=[\"' (,=])([A-Z]:\\[\w.\\-]+\.\w+)",
            _replace,
            line,
        )
        return line


# ── Module-level helpers ────────────────────────────────────────────


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences from LLM output.

    Handles fenced code blocks with or without a language tag.

    Args:
        text: Raw LLM response text.

    Returns:
        Text with fences stripped.
    """
    text = text.strip()
    # Remove opening fence: ```json or ```
    text = re.sub(r"^```\w*\s*\n?", "", text)
    # Remove closing fence
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _validate_challenge(data: dict) -> dict:
    """Validate and sanitise a parsed challenge dict.

    Ensures all required keys are present, types are correct, and
    string fields are truncated to prevent flooding.

    Args:
        data: Parsed JSON dict from LLM.

    Returns:
        Validated and sanitised challenge dict.

    Raises:
        KeyError: If a required key is missing.
        TypeError: If a value has the wrong type.
        ValueError: If estimated_minutes is out of range.
    """
    for key, expected_type in _REQUIRED_KEYS.items():
        if key not in data:
            msg = f"Missing required key: {key}"
            raise KeyError(msg)
        if not isinstance(data[key], expected_type):
            # Allow float for estimated_minutes and coerce to int
            if key == "estimated_minutes" and isinstance(data[key], float):
                data[key] = int(data[key])
            else:
                msg = (
                    f"Key '{key}' has type {type(data[key]).__name__}, "
                    f"expected {expected_type.__name__}"
                )
                raise TypeError(msg)

    # Validate estimated_minutes range
    if not 5 <= data["estimated_minutes"] <= 120:
        data["estimated_minutes"] = max(5, min(120, data["estimated_minutes"]))

    # Validate hints is a list of strings
    data["hints"] = [
        str(h)[:_MAX_FIELD_LEN] for h in data["hints"] if h
    ][:5]  # Cap at 5 hints

    # Truncate string fields
    for key in ("title", "description", "skill_name", "difficulty",
                "success_criteria"):
        if isinstance(data[key], str) and len(data[key]) > _MAX_FIELD_LEN:
            data[key] = data[key][:_MAX_FIELD_LEN]

    # Validate difficulty is one of the expected values
    if data["difficulty"] not in ("easy", "medium", "hard"):
        data["difficulty"] = "medium"

    return data


FALLBACK_CHALLENGES = {
    "sql_databases": {
        "easy": {
            "title": "Write a Raw Aggregate Query",
            "description": "Without using the ORM, write a raw SQL query that counts records grouped by a date field. Use your database's connection directly via cursor.execute().\n[dim](Generic challenge — add more commits to get personalized ones)[/dim]",
            "hints": ["Use GROUP BY DATE(created_at)", "Return results as a list of dicts"],
            "success_criteria": "Query runs without error and returns grouped counts",
            "estimated_minutes": 20,
            "fallback": True,
        },
        "medium": {
            "title": "Build a Transaction Scope",
            "description": "Create a context manager or decorator that wraps a database session in a transaction. Ensure it rolls back automatically if an exception occurs.\n[dim](Generic challenge — add more commits to get personalized ones)[/dim]",
            "hints": ["Use session.begin()", "Catch Exception to rollback"],
            "success_criteria": "Tests verify that raising an error rolls back the insert",
            "estimated_minutes": 40,
            "fallback": True,
        },
        "hard": {
            "title": "Implement Keyspace Sharding",
            "description": "Write a database routing layer that directs reads and writes to different tables or logical databases based on a user ID hash.\n[dim](Generic challenge — add more commits to get personalized ones)[/dim]",
            "hints": ["Use a hashing function like md5 to determine destination", "Wrap the connection factory"],
            "success_criteria": "Different user IDs get routed to their corresponding shards",
            "estimated_minutes": 60,
            "fallback": True,
        },
    },
}

for _s in [
    "async_concurrency", "data_structures", "regex_parsing", "error_handling",
    "api_design", "testing", "algorithms", "system_io", "security"
]:
    FALLBACK_CHALLENGES[_s] = {
        "easy": {
            "title": f"Basic {_s.replace('_', ' ').title()}",
            "description": f"Refactor a small component to use better {_s.replace('_', ' ')} patterns without copying from AI.\n[dim](Generic challenge — add more commits to get personalized ones)[/dim]",
            "hints": ["Review documentation for best practices", "Start with the simplest part"],
            "success_criteria": "The component behaves identically but uses the target skill properly",
            "estimated_minutes": 20,
            "fallback": True,
        },
        "medium": {
            "title": f"Intermediate {_s.replace('_', ' ').title()}",
            "description": f"Design a new module that relies heavily on {_s.replace('_', ' ')} paradigms to solve a recurring issue in your code.\n[dim](Generic challenge — add more commits to get personalized ones)[/dim]",
            "hints": ["Abstract common logic", "Write isolated tests first"],
            "success_criteria": "The module integrates cleanly without regressions",
            "estimated_minutes": 40,
            "fallback": True,
        },
        "hard": {
            "title": f"Advanced {_s.replace('_', ' ').title()}",
            "description": f"Undertake a major refactor of your project's core to implement scalable {_s.replace('_', ' ')} patterns across the board.\n[dim](Generic challenge — add more commits to get personalized ones)[/dim]",
            "hints": ["Draft an architecture plan", "Migrate one subsystem at a time"],
            "success_criteria": "System is demonstrably more robust or performant",
            "estimated_minutes": 60,
            "fallback": True,
        },
    }

def _fallback_challenge(
    skill_name: str, difficulty: str, estimated_minutes: int
) -> dict:
    """Return a hardcoded fallback challenge when LLM parsing fails.

    Args:
        skill_name: The skill the challenge targets.
        difficulty: The difficulty tier.
        estimated_minutes: The estimated completion time.

    Returns:
        A safe, static challenge dict.
    """
    if skill_name in FALLBACK_CHALLENGES and difficulty in FALLBACK_CHALLENGES[skill_name]:
        chall = FALLBACK_CHALLENGES[skill_name][difficulty].copy()
        chall["skill_name"] = skill_name
        chall["difficulty"] = difficulty
        return chall
        
    return {
        "title": f"Practice {skill_name.replace('_', ' ').title()}",
        "description": (
            f"Write a small program that exercises your "
            f"{skill_name.replace('_', ' ')} skills. "
            f"Pick a real problem from your current project and solve it "
            f"without AI assistance. Focus on understanding every line.\n"
            f"[dim](Generic challenge — add more commits to get personalized ones)[/dim]"
        ),
        "skill_name": skill_name,
        "difficulty": difficulty,
        "estimated_minutes": estimated_minutes,
        "hints": [
            "Start with the simplest possible version",
            "Add error handling after the core logic works",
        ],
        "success_criteria": (
            "The program runs correctly and you can explain every "
            "line of code you wrote."
        ),
        "fallback": True,
    }
