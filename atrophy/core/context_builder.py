import re
import subprocess
from collections import Counter
from pathlib import Path
import tomllib  # Python 3.11+

class ContextBuilder:
    def __init__(self, repo_path: Path):
        self._repo = repo_path

    def build_challenge_context(self, skill: str, commits: list[dict], language: str) -> str:
        parts = []

        # SOURCE 1: Recent file structure
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=str(self._repo),
                capture_output=True,
                text=True,
                shell=False,
                timeout=5
            )
            tracked_files = set(result.stdout.splitlines())
            
            file_counts = Counter()
            for c in commits:
                for f in c.get("files_changed", []):
                    if f in tracked_files:
                        file_counts[f] += 1
            
            top_files = [f for f, _ in file_counts.most_common(15)]
            if not top_files:
                top_files = list(tracked_files)[:15]

            s1 = "Project files (most active):\n" + "\n".join(f"  {f}" for f in top_files)
            parts.append(s1[:300])
        except Exception:
            pass

        # SOURCE 2: Skill-relevant code snippet
        snippet_part = ""
        from atrophy.core.skill_mapper import SKILL_PATTERNS
        pattern_def = SKILL_PATTERNS.get(skill)
        if pattern_def:
            keywords = pattern_def.get("keywords", [])
            found = False
            for c in commits:
                if found: break
                if c.get("classification", "human") == "ai": continue
                
                diff_text = c.get("diff_text", "")
                if not diff_text: continue
                
                relevant_lines = []
                for line in diff_text.splitlines():
                    if not line.startswith("+"): continue
                    clean_line = line[1:]
                    if any(kw in clean_line for kw in keywords):
                        # Strip full paths
                        def _replace(match: re.Match) -> str:
                            return Path(match.group()).name
                        clean_line = re.sub(r"(?<=[\"' (,=])(/[\w./-]+\.\w+)", _replace, clean_line)
                        clean_line = re.sub(r"(?<=[\"' (,=])([A-Z]:\\[\w.\\-]+\.\w+)", _replace, clean_line)
                        relevant_lines.append(clean_line)
                
                if relevant_lines:
                    sample = "\n".join(relevant_lines)
                    files = c.get("files_changed", [])
                    fname = Path(files[0]).name if files else "code"
                    
                    snippet = f"Your code in {fname}:\n```python\n{sample}\n```"
                    if len(snippet) > 500:
                        snippet = snippet[:485] + "\n# ... (truncated)\n```"
                    snippet_part = snippet
                    found = True
        
        if snippet_part:
            parts.append(snippet_part)

        # SOURCE 3 & 4: Tech stack detection
        deps = []
        
        try:
            pyproject = self._repo / "pyproject.toml"
            if pyproject.exists():
                with pyproject.open("rb") as f:
                    data = tomllib.load(f)
                if "project" in data and "dependencies" in data["project"]:
                    for dep in data["project"]["dependencies"]:
                        deps.append(re.split(r'[>=<~]', dep)[0].strip())
                if "tool" in data and "poetry" in data["tool"] and "dependencies" in data["tool"]["poetry"]:
                    deps.extend(data["tool"]["poetry"]["dependencies"].keys())
        except Exception:
            pass

        try:
            reqs = self._repo / "requirements.txt"
            if reqs.exists() and not deps:
                content = reqs.read_text()
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        deps.append(re.split(r'[>=<~]', line)[0].strip())
        except Exception:
            pass

        try:
            pkg_json = self._repo / "package.json"
            if pkg_json.exists():
                import json
                data = json.loads(pkg_json.read_text())
                if "dependencies" in data:
                    deps.extend(data["dependencies"].keys())
                if "devDependencies" in data:
                    deps.extend(data["devDependencies"].keys())
        except Exception:
            pass

        try:
            gomod = self._repo / "go.mod"
            if gomod.exists():
                content = gomod.read_text()
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("module "):
                        deps.append(line.split()[1])
                    elif not line.startswith("go ") and not line.startswith("require (") and not line.startswith(")"):
                        parts_line = line.split()
                        if len(parts_line) > 0 and "." in parts_line[0]:
                            deps.append(parts_line[0].replace('"', ''))
        except Exception:
            pass

        deps = [d for d in deps if d and d.lower() != "python"]
        top_deps = deps[:5]
        
        if top_deps:
            s3 = f"Dependencies: {', '.join(top_deps)}"
            parts.append(s3[:200])

        # Source 4
        framework = "Unknown"
        dep_lower = [d.lower() for d in deps]
        if "fastapi" in dep_lower: framework = "FastAPI"
        elif "django" in dep_lower: framework = "Django"
        elif "flask" in dep_lower: framework = "Flask"
        elif "react" in dep_lower: framework = "React"
        elif "next" in dep_lower: framework = "Next.js"
        elif "vue" in dep_lower: framework = "Vue"
        elif "express" in dep_lower: framework = "Express"
        elif "spring" in dep_lower: framework = "Spring Boot"
        elif "rails" in dep_lower: framework = "Ruby on Rails"
        elif "laravel" in dep_lower: framework = "Laravel"
        else:
            if "pyproject.toml" in [f.name for f in self._repo.iterdir()]: framework = "Standard Python"
            elif "package.json" in [f.name for f in self._repo.iterdir()]: framework = "Node.js app"
        
        s4 = f"Primary language: {language} | Framework: {framework} (detected from imports)"
        parts.append(s4)

        full_context = "\n\n".join(parts)
        return full_context[:1200]
