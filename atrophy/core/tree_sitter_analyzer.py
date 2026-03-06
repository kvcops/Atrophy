"""Tree-sitter AST analyzer for skill detection.

Uses tree-sitter to parse code diffs into ASTs and count skill-relevant
node types. Falls back to keyword scanning in string/identifier contexts
for skills without AST node mappings. Lazy-loads parsers per language.

Security:
    - Only reads diff lines that start with ``+`` (added lines).
    - No subprocess, file I/O, or network calls.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── Supported languages ─────────────────────────────────────────────

SUPPORTED_EXTENSIONS: dict[str, str] = {
    "py": "python",
    "ts": "typescript",
    "js": "javascript",
    "rs": "rust",
    "go": "go",
    "java": "java",
    "rb": "ruby",
    "cpp": "cpp",
    "c": "c",
}

# ── AST node → skill mapping ───────────────────────────────────────

SKILL_NODE_MAP: dict[str, list[str]] = {
    "async_concurrency": [
        "await_expression",
        "async_function_definition",
        "async_statement",
        "go_statement",          # Go goroutines
        "spawn_expression",      # Rust tokio::spawn
        "async",                 # keyword node
    ],
    "data_structures": [
        "class_definition",
        "struct_item",
        "type_declaration",
        "interface_declaration",
        "enum_item",
        "class_declaration",
        "decorated_definition",
    ],
    "error_handling": [
        "try_statement",
        "except_clause",
        "catch_clause",
        "raise_statement",
        "throw_statement",
        "finally_clause",
    ],
    "testing": [
        # function definitions starting with "test_" are counted via
        # the special _is_test_function check, not here.
        "assert_statement",
    ],
    "algorithms": [
        "for_statement",
        "for_in_statement",
        "while_statement",
    ],
}

# Skills that use keyword fallback on string literals / identifiers
# instead of AST nodes (these concepts aren't structural).
KEYWORD_FALLBACK_SKILLS: set[str] = {
    "sql_databases",
    "regex_parsing",
    "api_design",
    "system_io",
    "security",
}

# Identifiers and string-literal node types per language
_STRING_IDENS: set[str] = {
    "string",
    "string_literal",
    "string_content",
    "template_string",
    "identifier",
    "attribute",
    "property_identifier",
    "field_identifier",
    "call_expression",
    "raw_string_literal",
    "interpreted_string_literal",
    "method_invocation",
}


class TreeSitterAnalyzer:
    """AST-based skill detector using tree-sitter.

    Parses code diffs into syntax trees and counts AST node types
    that correspond to coding skills. For skills that can't be detected
    structurally (e.g. SQL, regex), falls back to keyword scanning
    but only on identifiers and string literals — not comments or
    docstrings.
    """

    def __init__(self) -> None:
        """Initialize with empty parser cache."""
        self._parsers: dict[str, object] = {}

    def _get_parser(self, lang: str):
        """Lazy-load and cache a tree-sitter parser for a language.

        Args:
            lang: Language name (e.g. ``"python"``).

        Returns:
            A tree-sitter Parser, or None if loading fails.
        """
        if lang in self._parsers:
            return self._parsers[lang]

        try:
            from tree_sitter_language_pack import get_parser

            parser = get_parser(lang)
            self._parsers[lang] = parser
            return parser
        except Exception:
            logger.debug(
                "Failed to load tree-sitter parser for %s", lang,
            )
            self._parsers[lang] = None
            return None

    def is_supported(self, extension: str) -> bool:
        """Check if a file extension has tree-sitter support.

        Args:
            extension: File extension without dot (e.g. ``"py"``).

        Returns:
            True if the extension maps to a supported language.
        """
        return extension in SUPPORTED_EXTENSIONS

    def analyze_diff(
        self,
        diff_text: str,
        file_extension: str,
        keywords_by_skill: dict[str, list[str]] | None = None,
    ) -> dict[str, int]:
        """Analyze a diff using tree-sitter AST walking.

        Extracts added lines (``+`` prefix), reconstructs code,
        parses with tree-sitter, then:
        1. Counts AST node types for structural skills.
        2. Falls back to keyword scanning on string/identifier
           nodes for non-structural skills.

        Args:
            diff_text: Raw unified diff text.
            file_extension: Extension without dot (e.g. ``"py"``).
            keywords_by_skill: Mapping of skill → keyword list for
                fallback skills. If None, fallback is skipped.

        Returns:
            Dict mapping skill names to hit counts.
        """
        lang = SUPPORTED_EXTENSIONS.get(file_extension)
        if lang is None:
            return {}

        parser = self._get_parser(lang)
        if parser is None:
            return {}

        # Extract only added lines from the diff
        code_lines: list[str] = []
        for line in diff_text.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                code_lines.append(line[1:])  # strip the "+"

        if len(code_lines) < 3:
            return {}

        code = "\n".join(code_lines)

        try:
            tree = parser.parse(code.encode("utf-8"))
        except Exception:
            logger.debug("tree-sitter parse failed for %s", lang)
            return {}

        root = tree.root_node
        hits: dict[str, int] = {}

        # Walk the entire AST
        self._walk_ast(root, hits, code_lines)

        # Keyword fallback for non-structural skills
        if keywords_by_skill:
            self._keyword_fallback(
                root, code, keywords_by_skill, hits,
            )

        return hits

    def _walk_ast(
        self,
        node,
        hits: dict[str, int],
        code_lines: list[str],
    ) -> None:
        """Recursively walk AST and count skill-relevant nodes.

        Args:
            node: Current tree-sitter Node.
            hits: Accumulator dict to update in-place.
            code_lines: Source code lines for test function check.
        """
        node_type = node.type

        # Check if this node type maps to a skill
        for skill_name, node_types in SKILL_NODE_MAP.items():
            if node_type in node_types:
                hits[skill_name] = hits.get(skill_name, 0) + 1

        # Special handling: test function detection
        if node_type in (
            "function_definition", "function_declaration",
        ):
            func_name = self._get_function_name(node)
            if func_name and func_name.startswith("test_"):
                hits["testing"] = hits.get("testing", 0) + 1

        # Check for call expressions that look like test assertions
        if node_type == "call":
            callee = self._get_callee_name(node)
            if callee in ("expect", "assert_eq", "assert_ne"):
                hits["testing"] = hits.get("testing", 0) + 1

        # Recurse
        for child in node.children:
            self._walk_ast(child, hits, code_lines)

    def _keyword_fallback(
        self,
        root,
        code: str,
        keywords_by_skill: dict[str, list[str]],
        hits: dict[str, int],
    ) -> None:
        """Scan string/identifier nodes for keyword-based skills.

        Only searches inside identifiers, string literals, and
        attribute accesses — never in comments or docstrings.

        Args:
            root: The AST root node.
            code: Full reconstructed source code.
            keywords_by_skill: Mapping of skill → keyword list.
            hits: Accumulator dict to update in-place.
        """
        # Collect text from string/identifier nodes
        identifier_text: list[str] = []
        self._collect_text_nodes(root, code, identifier_text)
        joined = "\n".join(identifier_text)

        for skill_name, keywords in keywords_by_skill.items():
            if skill_name not in KEYWORD_FALLBACK_SKILLS:
                continue
            for keyword in keywords:
                count = joined.count(keyword)
                if count > 0:
                    hits[skill_name] = (
                        hits.get(skill_name, 0) + count
                    )

    def _collect_text_nodes(
        self, node, code: str, result: list[str],
    ) -> None:
        """Recursively collect text from identifier/string nodes.

        Args:
            node: Current tree-sitter Node.
            code: Source code bytes decoded.
            result: List to append extracted text to.
        """
        if node.type in _STRING_IDENS:
            start = node.start_byte
            end = node.end_byte
            text = code[start:end]
            if text:
                result.append(text)

        for child in node.children:
            self._collect_text_nodes(child, code, result)

    @staticmethod
    def _get_function_name(node) -> str | None:
        """Extract function name from a function definition node.

        Args:
            node: A function_definition tree-sitter Node.

        Returns:
            The function name, or None.
        """
        for child in node.children:
            if child.type in ("identifier", "name"):
                return child.text.decode("utf-8") if isinstance(
                    child.text, bytes
                ) else str(child.text)
        return None

    @staticmethod
    def _get_callee_name(node) -> str | None:
        """Extract callee name from a call expression node.

        Args:
            node: A call tree-sitter Node.

        Returns:
            The callee name, or None.
        """
        for child in node.children:
            if child.type in ("identifier", "name"):
                return child.text.decode("utf-8") if isinstance(
                    child.text, bytes
                ) else str(child.text)
            if child.type == "attribute":
                # e.g. self.assertEqual → get "assertEqual"
                for grandchild in child.children:
                    if grandchild.type in (
                        "identifier", "name",
                    ):
                        text = (
                            grandchild.text.decode("utf-8")
                            if isinstance(grandchild.text, bytes)
                            else str(grandchild.text)
                        )
                        return text
        return None
