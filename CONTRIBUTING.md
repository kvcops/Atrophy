# Contributing to atrophy

## Why contribute?
We believe engineering skills are muscles that require continuous, hard practice to maintain. `atrophy` is an open source tool dedicated to measuring and fighting back against the quiet erosion of human capability in the AI era.

## How to add a new skill category
1. Identify a skill that has clear, detectable code patterns.
2. Open `atrophy/core/skill_mapper.py`.
3. Locate the `SKILL_PATTERNS` dictionary.
4. Add your new skill following this exact schema:
```python
"new_skill": {
    "keywords": ["specific_function", "import_path"],
    "file_extensions": ["py", "js"],
    "emoji": "🛠️",
    "description": "Short description of the skill."
}
```
5. Add a test in `tests/test_skill_mapper.py` with mock code that matches your new keywords.

## How to add a new LLM provider
1. Create a new file in `atrophy/providers/`, like `my_provider.py`.
2. Implement the `BaseLLMProvider` interface from `atrophy/providers/base.py`.
3. Add any required API keys (as `SecretStr`) to `atrophy/config.py`.
4. Register your provider in `atrophy/providers/__init__.py`.

## How to improve the AI detector
The AI detector relies on 5 statistical signals (Velocity, Burstiness, Formatting, Message, Entropy). If you want to contribute, you can submit PRs to tweak the `SIGNAL_WEIGHTS` in `AIDetector` or propose new statistical heuristics (e.g., AST uniformity or edit distance profiles) that improve the ~75% accuracy baseline. Provide benchmark data to support weight adjustments!

## Good first issues
1. Add Swift/Kotlin/Rust language support to skill patterns
2. Add a `atrophy compare` command (compare two time periods)
3. Improve the Textual dashboard with Plotext charts
4. Add a `atrophy config` command to change settings without re-init
5. Add test coverage for GitScanner
6. Write a brew formula for macOS install
