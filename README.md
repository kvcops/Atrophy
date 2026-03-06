# 🧬 atrophy

> Your coding skills have a half-life. atrophy measures it.

[![PyPI version](https://img.shields.io/pypi/v/atrophy.svg)](https://pypi.org/p/atrophy)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)]()

---

## The thing nobody talks about

We all felt it happen. At first, Copilot was just a faster autocomplete—a way to skip the boilerplate and get straight to the interesting problems. Then came Claude, ChatGPT, and Cursor. Suddenly, the "interesting problems" were being solved for us, too. We justified it by calling ourselves "architects" or "directors," pointing at the mountain of shipped features as proof of our elevated productivity.

But in the quiet moments between prompts, there's a creeping realization. When was the last time you wrote a complex regex from scratch without pasting a sample into a chat window? How long does it take you to implement a standard recursive algorithm or a SQL window function now? The muscle memory is fading. We are building faster than ever, but our fundamental, raw engineering skills are slowly atrophying.

This isn't burnout. Burnout is exhaustion from overwork. This is the opposite—it's the soft comfort of continuous, effortless delivery. You are productive, your PRs are getting merged, and your managers are happy. But underneath the surface, you're slowly losing your edge. You're outsourcing the friction, and friction is where learning happens.

`atrophy` is the honest mirror you didn't know you needed. It quietly analyzes your git commit history to measure exactly which skills you're still exercising and which ones you've handed over entirely to AI. It doesn't judge, it doesn't report to your boss, and it doesn't stop you from using AI. It just gives you the raw data on your own skill degradation, and offers personalized, hyper-targeted mini-challenges to help you win back the specific muscles you're losing.

---

## Install

Use `uv` to install `atrophy`. We never suggest using `pip` directly.

```bash
uv tool install atrophy
```

## 2-minute quickstart

```bash
cd your-project
atrophy init           # Connect to your repo (one time)
atrophy scan           # Analyze last 180 days of commits
atrophy report         # See your skill profile
atrophy dashboard      # Terminal dashboard
atrophy challenge --generate  # Get this week's challenges
```

## What atrophy measures

| Skill | Description | Signal Detected |
|-------|-------------|-----------------|
| 🧠 **Algorithms** | Data structures, recursion, complex logic | Abstract graph/tree traversals, custom sorting, DP |
| 🔣 **Regex** | Regular expressions | Non-trivial regex patterns, capture groups, lookaheads |
| 🗄️ **SQL** | Database queries and schema design | Window functions, CTEs, complex joins, indexing |
| 🏗️ **Architecture**| System design and abstraction | Interface definitions, dependency injection, state machines |
| 🛡️ **Security** | Safe encoding, cryptography, validation | Parameterized queries, CSRF tokens, input sanitization |
| 🚦 **Concurrency** | Async, threading, multiprocessing | Mutexes, concurrent queues, task groups, promises |
| 🧪 **Testing** | Mocks, fixtures, property-based tests | Custom test fixtures, deep mocking, parameterized tests |
| 📦 **DevOps** | CI/CD, Docker, infrastructure as code | Complex bash pipelines, workflow logic, terraform interpolation |
| 🎨 **CSS/UI** | Complex styling, layout grids, animations | CSS Grid, keyframes, fluid typography, media queries |
| 🔧 **Tooling** | Build scripts, parsers, AST manipulation | Custom parsers, code generation, AST transformations |

## FAQ

**Q: Does my code leave my machine?**  
A: No. atrophy runs 100% locally. Git history stays local. Challenges use YOUR API key, direct to the LLM — atrophy is just the pipe.

**Q: Is the AI detection accurate?**  
A: It uses 5 statistical signals and is ~75% accurate in our testing. Treat it as a mirror, not a verdict.

**Q: Can I use it without an LLM API key?**  
A: Yes. `atrophy init` lets you skip LLM setup. You just won't get personalized challenges.

**Q: Can my team use it?**  
A: Yes — each person runs it locally. The GitHub Action posts a summary on PRs.

## Built with atrophy

[See the tools built with renewed coding skills](built-with-atrophy.md)

## Contributing

[Read our contributing guidelines](CONTRIBUTING.md)

Star the repo if atrophy makes you uncomfortable in a good way. ⭐
