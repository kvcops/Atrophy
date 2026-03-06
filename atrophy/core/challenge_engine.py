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
You are a coding skills coach. Generate a hands-on coding challenge that helps a
developer practice a specific forgotten skill. The challenge must:
- Be completable in the estimated time (not a tutorial, a real mini-task)
- Reference the developer's actual tech stack and codebase patterns
- Have clear success criteria the developer can verify themselves
- NOT use the words "LeetCode", "algorithm challenge", or "interview problem"

Respond ONLY in valid JSON. No markdown fences. No preamble.\
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
        code_samples: dict[str, str],
        top_skill: str,
    ) -> list[dict]:
        """Generate up to 3 challenges for dead-zone skills.

        Selects the first 3 dead zones and assigns escalating
        difficulty tiers (easy → medium → hard). For each, calls the
        LLM provider and sanitises the response before returning.

        Args:
            dead_zones: Skill names in the dead zone, ordered by
                urgency (from ``SkillMapper.get_dead_zones``).
            language: The developer's primary programming language.
            code_samples: Mapping of ``{skill_name: sample_code}``.
                Provided by ``get_code_sample`` from commit history.
            top_skill: The developer's strongest skill (for contrast).

        Returns:
            List of valid challenge dicts. May be fewer than 3 if
            the LLM fails for some prompts — never crashes.
        """
        # Select up to 3 dead zones
        selected = dead_zones[:3]
        if not selected:
            return []

        challenges: list[dict] = []
        for idx, skill_name in enumerate(selected):
            difficulty, estimated_minutes = _DIFFICULTY_TIERS[
                min(idx, len(_DIFFICULTY_TIERS) - 1)
            ]
            code_sample = code_samples.get(skill_name, "")
            user_prompt = self._build_user_prompt(
                skill_name=skill_name,
                language=language,
                difficulty=difficulty,
                estimated_minutes=estimated_minutes,
                code_sample=code_sample,
            )

            challenge = await self._call_and_parse(
                user_prompt=user_prompt,
                skill_name=skill_name,
                difficulty=difficulty,
                estimated_minutes=estimated_minutes,
            )
            challenges.append(challenge)

        return challenges

    def get_code_sample(
        self,
        commits: list[dict],
        skill_name: str,
        max_chars: int = 400,
    ) -> str:
        """Extract a code sample from human commits for a given skill.

        Searches for commits classified as human that exercised the
        target skill. Extracts added diff lines that match skill
        keywords and truncates to ``max_chars``.

        SECURITY: File paths are stripped to basenames only — full
        paths are never included in samples sent to the LLM.

        Args:
            commits: Analyzed commit dicts (must have
                ``classification``, ``diff_text``, ``files_changed``).
            skill_name: The skill to find relevant code for.
            max_chars: Maximum characters in the returned sample.

        Returns:
            A truncated code snippet, or empty string if none found.
        """
        from atrophy.core.skill_mapper import SKILL_PATTERNS

        pattern_def = SKILL_PATTERNS.get(skill_name)
        if pattern_def is None:
            return ""

        keywords = pattern_def["keywords"]

        # Search human commits for relevant diffs
        for commit in commits:
            if commit.get("classification") != "human":
                continue

            diff_text = commit.get("diff_text", "")
            if not diff_text:
                continue

            # Extract only added lines matching skill keywords
            relevant_lines: list[str] = []
            for line in diff_text.splitlines():
                # Diff added lines start with "+"
                if not line.startswith("+"):
                    continue
                # Strip the leading "+" for readability
                clean_line = line[1:]
                if any(kw in clean_line for kw in keywords):
                    # SECURITY: strip any full file paths to basename
                    clean_line = self._strip_paths(clean_line)
                    relevant_lines.append(clean_line)

            if relevant_lines:
                sample = "\n".join(relevant_lines)
                # Truncate to max_chars
                if len(sample) > max_chars:
                    sample = sample[:max_chars] + "\n# ... (truncated)"
                return sample

        return ""

    # ── Private helpers ─────────────────────────────────────────────

    @staticmethod
    def _build_user_prompt(
        skill_name: str,
        language: str,
        difficulty: str,
        estimated_minutes: int,
        code_sample: str,
    ) -> str:
        """Build the user prompt for a single challenge request.

        Args:
            skill_name: The skill to practice.
            language: Developer's primary language.
            difficulty: easy / medium / hard.
            estimated_minutes: Target completion time.
            code_sample: Relevant code from the developer's repo.

        Returns:
            Formatted prompt string.
        """
        sample_section = (
            code_sample
            if code_sample
            else f"No sample available — use idiomatic patterns for {language}"
        )
        return (
            f"Developer profile:\n"
            f"- Primary language: {language}\n"
            f"- Skill to practice: {skill_name}\n"
            f"- Difficulty: {difficulty}\n"
            f"- Time available: {estimated_minutes} minutes\n"
            f"\n"
            f"Real code from their project (for context):\n"
            f"{sample_section}\n"
            f"\n"
            f"Generate a challenge JSON object with these exact keys:\n"
            f'{{\n'
            f'  "title": "short catchy title (max 8 words)",\n'
            f'  "description": "clear problem statement '
            f'(3-4 sentences, specific task to build)",\n'
            f'  "skill_name": "{skill_name}",\n'
            f'  "difficulty": "{difficulty}",\n'
            f'  "estimated_minutes": {estimated_minutes},\n'
            f'  "hints": ["hint 1", "hint 2"],\n'
            f'  "success_criteria": "one sentence describing '
            f'how they\'ll know it\'s done"\n'
            f'}}'
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
            return _validate_challenge(parsed)

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
    return {
        "title": f"Practice {skill_name.replace('_', ' ').title()}",
        "description": (
            f"Write a small program that exercises your "
            f"{skill_name.replace('_', ' ')} skills. "
            f"Pick a real problem from your current project and solve it "
            f"without AI assistance. Focus on understanding every line."
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
    }
