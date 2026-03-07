<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=venom&height=300&text=ATROPHY&fontSize=120&color=0:8B00FF,50:9932CC,100:4B0082&fontColor=ffffff&stroke=9932CC&strokeWidth=3&animation=fadeIn&desc=Your%20coding%20skills%20have%20a%20half-life.%20atrophy%20measures%20it.&descSize=19&descAlignY=78&fontAlignY=45" width="100%" />
</p>


<br/>

<p align="center">
  <a href="https://pypi.org/p/atrophy">
    <img src="https://img.shields.io/pypi/v/atrophy?style=for-the-badge&logo=pypi&logoColor=white&color=8B00FF&labelColor=12001f" alt="PyPI"/>
  </a>&nbsp;
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white&labelColor=12001f"/>&nbsp;
  <img src="https://img.shields.io/badge/Powered%20by-uv-DE5FE9?style=for-the-badge&logoColor=white&labelColor=12001f"/>&nbsp;
  <img src="https://img.shields.io/badge/AST-Tree--sitter-FF6B6B?style=for-the-badge&labelColor=12001f"/>&nbsp;
  <img src="https://img.shields.io/badge/TUI-Textual-9932CC?style=for-the-badge&labelColor=12001f"/>&nbsp;
  <img src="https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge&logo=opensourceinitiative&logoColor=white&labelColor=12001f"/>
</p>

<p align="center">
  <a href="#-the-problem-nobody-talks-about">🚨 Problem</a> &nbsp;·&nbsp;
  <a href="#-what-atrophy-does">💡 What It Does</a> &nbsp;·&nbsp;
  <a href="#-how-it-works">⚙️ How It Works</a> &nbsp;·&nbsp;
  <a href="#-installation">🚀 Install</a> &nbsp;·&nbsp;
  <a href="#-quickstart-2-minutes">⚡ Quickstart</a> &nbsp;·&nbsp;
  <a href="#-the-10-skill-disciplines">🔬 Skills</a> &nbsp;·&nbsp;
  <a href="#-llm-providers">🔌 Providers</a> &nbsp;·&nbsp;
  <a href="#-faq">❓ FAQ</a>
</p>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=3" width="100%"/>

<br/>

## 🚨 The Problem Nobody Talks About

<img align="right" width="155" src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Smilies/Anxious%20Face%20with%20Sweat.png"/>

You use Cursor. You use Copilot. You use Claude. You are shipping faster than ever — PRs merging, tickets closing, metrics looking great.

But something quiet is happening underneath all of that.

```
❓  When did you last write a regex without pasting it into a chat window?
❓  Can you still write a raw SQL GROUP BY query from memory?
❓  If your AI tool broke right now — could you debug the async race condition yourself?
```

AI tools are genuinely incredible. But here is what nobody says out loud:

> **Every time AI does the hard part for you, your brain skips that rep. And skipped reps lead to atrophy.**

You are outsourcing the friction. Friction is where learning happens. Your skills are quietly wasting away — and until now, there was no tool to measure it, show it to you, or help you fight it.

That is what `atrophy` is for.

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=3" width="100%"/>

<br/>

## 💡 What atrophy Does

<img align="left" width="145" src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Smilies/Alien%20Monster.png"/>

&nbsp;&nbsp;`atrophy` connects to your local git history and does four things:

&nbsp;&nbsp;**1. Measures what YOU actually wrote** — using statistical signals, it separates commits you personally wrote from commits that were clearly AI-generated.

&nbsp;&nbsp;**2. Maps your skill health** — it tracks 10 engineering disciplines (SQL, algorithms, testing, security, etc.) and scores how actively you exercise each one yourself.

&nbsp;&nbsp;**3. Shows you the decay** — a beautiful terminal dashboard reveals which skills are going dark and how fast, with a month-by-month timeline.

&nbsp;&nbsp;**4. Fights back for you** — every week, it generates 3 personalized coding challenges targeting your dead zones, using real patterns from your own codebase. Not LeetCode. Not generic tutorials. Your forgotten skills, in your actual stack.

<br clear="left"/>

**The key thing:** Everything runs 100% locally on your machine. Your source code never leaves your computer. `atrophy` only reads your git history — it never writes to your repo, never uploads your code, and never phones home.

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=3" width="100%"/>

<br/>

## ⚙️ How It Works

### Step 1 — Reading Your Git History

When you run `atrophy scan`, it walks your entire commit history for the past 180 days (configurable). It reads the actual diff of each commit — the lines of code added, removed, and changed. It filters out noise automatically: dependency lock files, auto-generated code, minified files, and merge commits are all ignored so they don't skew your results.

### Step 2 — Separating Human Commits from AI Commits

This is the statistical heart of `atrophy`. It uses **5 signals** combined into a single probability score for each commit:

| Signal | What It Looks At | Why It Works |
|---|---|---|
| **Commit Velocity** | Lines added per minute vs. your personal average | AI pastes 200 lines in 8 seconds. Humans type |
| **Burstiness Score** | How uniform or varied your line lengths are | AI code is suspiciously uniform. Human code is messy |
| **Entropy Analysis** | Character distribution patterns in the code | AI produces "expected" code. Humans are quirky |
| **Formatter Presence** | Whether formatting is machine-perfect | Running ruff/black yourself? atrophy accounts for it |
| **Message Depth** | Commit message patterns and specificity | "fix" at 2am is you. "feat: add JWT middleware" at 2am is Cursor |

**Important:** atrophy builds a **Personal Baseline** from your oldest commits — from before you were using AI heavily. It calibrates all signals to *your* natural pace, not some generic average. A developer who types fast and always uses conventional commits won't be falsely flagged as AI-assisted. The tool adapts to you.

This is a probabilistic mirror for self-reflection. It is not a verdict, not a judge, and not accurate enough to evaluate anyone else. Treat it as honest data about yourself.

### Step 3 — Mapping Skills with 3-Layer Detection

Once `atrophy` knows which commits you personally wrote, it figures out *which skills* you exercised. It uses three layers in priority order:

**Layer 1 — Tree-sitter AST Analysis (most accurate)**
Tree-sitter is a real code parser — the same technology that powers VS Code's syntax highlighting. `atrophy` uses it to build an Abstract Syntax Tree of your code changes and count actual code structures: async functions, try/catch blocks, SQL calls, custom classes, test assertions, and more. It understands code structure, not just text. It works for Python, TypeScript, JavaScript, Go, Rust, Java, Ruby, C++, and more.

**Layer 2 — LLM Semantic Classification (for complex or unknown cases)**
For recent commits (last 90 days) where the language is less common or the skill is ambiguous, `atrophy` can optionally send a short anonymized snippet to your configured LLM to ask "what skill category is this?" — using your own API key, direct to the provider. No middleman.

**Layer 3 — Keyword Fallback (always available, zero cost)**
If tree-sitter doesn't support the language and you have no LLM configured, `atrophy` falls back to smart keyword scanning — but only inside actual code (not comments or string literals), using language-specific comment strippers.

### Step 4 — Generating Your Weekly Challenges

Every week, `atrophy challenge --generate` picks your top 3 dead zones and asks your configured LLM to create personalized exercises. Before sending anything to the LLM, `atrophy` builds a rich context package:
- The most-committed files in your project (by name, not content)
- A short sample of real code you personally wrote in that skill area
- Your detected tech stack (frameworks, dependencies)
- Your primary language

The result: challenges that say "add a raw aggregate query to your existing User model using the patterns already in your codebase" — not "implement a binary search tree."

If the LLM returns something generic or hallucinated, `atrophy` detects this automatically and swaps in a hand-crafted fallback challenge. You always get something useful.

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=3" width="100%"/>

<br/>

## 🚀 Installation

<img align="right" width="115" src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Rocket.png"/>

We recommend **[`uv`](https://github.com/astral-sh/uv)** — a Rust-powered Python package manager that is 100x faster than pip and keeps `atrophy` isolated from your system Python.

```bash
# Install uv first (if you don't have it)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install atrophy globally
uv tool install atrophy
```

**Prefer plain pip?**
```bash
pip install atrophy
```

**Verify the install:**
```bash
atrophy --version
```

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=3" width="100%"/>

<br/>

## ⚡ Quickstart (2 Minutes)

```bash
# ① Go to any project with git history
cd your-project

# ② One-time setup — connects atrophy to this repo
#    It will ask for your git email and optionally an LLM provider
atrophy init

# ③ Scan the last 180 days of commits (takes 10–60 seconds depending on repo size)
atrophy scan

# ④ Read your full skill report in the terminal
atrophy report

# ⑤ Launch the interactive animated dashboard
atrophy dashboard

# ⑥ Generate this week's personalized skill challenges
atrophy challenge --generate

# ⑦ Export your weekly digest to Markdown (paste into Obsidian, Notion, etc.)
atrophy digest --open
```

<details>
<summary><b>📸 What does the terminal dashboard look like?</b></summary>
<br>

```
╔══════════════════════════════════════════════════════════════════════════╗
║  🧬 ATROPHY  ·  Coding Fingerprint  ·  yourname@email.com  ·  2 min ago ║
╠═══════════════════════════╦════════════════════════════════════════════╣
║  YOUR SKILL HEALTH        ║  HUMAN vs AI RATIO (last 6 months)        ║
║                           ║                                            ║
║  🧠  algorithms    72  ▓▓▓▓▓▓▓░ ↑  ║  Oct  ████████████████░░░░  79%  ║
║  🛡️   security     68  ▓▓▓▓▓▓░░ →  ║  Nov  ████████████░░░░░░░░  61%  ║
║  🌐  api_design    85  ▓▓▓▓▓▓▓▓ ↑  ║  Dec  ████████░░░░░░░░░░░░  48%  ║
║  ⚡  async         61  ▓▓▓▓▓▓░░ ↓  ║  Jan  ██████████░░░░░░░░░░  53%  ║
║  🗄️   sql          29  ▓▓░░░░░░ ⚠  ║  Feb  ████████████░░░░░░░░  59%  ║
║  🔍  regex         18  ▓░░░░░░░ ⚠  ║  Mar  ██████████████░░░░░░  67% ↑║
║                           ║                                            ║
╠═══════════════════════════╬════════════════════════════════════════════╣
║  ⚡ SKILLS TO REVISIT     ║  🏆 THIS WEEK'S WINS                       ║
║                           ║                                            ║
║  • sql_databases  62 days ║  ✨ error_handling improved +14 pts        ║
║  • regex_parsing  41 days ║  🔥 testing: dead zone cleared!            ║
║  • testing        38 days ║  📈 Best human ratio in 3 months           ║
╠═══════════════════════════╩════════════════════════════════════════════╣
║  🔥 Streak: 3 weeks  |  Pending challenges: 2  |  [Q]uit  [R]efresh   ║
╚══════════════════════════════════════════════════════════════════════════╝
```
</details>

<details>
<summary><b>📋 What does <code>atrophy report</code> look like?</b></summary>
<br>

```
┌─────────────────────────────────────────────────────────────────┐
│  📊 Your Coding Fingerprint                                     │
│  yourusername · Python developer · Active since 2023            │
├─────────────────┬──────────────┬───────────┬────────────────────┤
│  Skill          │  Score       │  Trend    │  Last Used         │
├─────────────────┼──────────────┼───────────┼────────────────────┤
│  api_design     │  ████████ 85 │  ↑ up     │  2 days ago        │
│  algorithms     │  ███████░ 72 │  ↑ up     │  5 days ago        │
│  security       │  ██████░░ 68 │  → stable │  1 week ago        │
│  async          │  ██████░░ 61 │  ↓ down   │  3 weeks ago       │
│  sql_databases  │  ██░░░░░░ 29 │  ↓ down   │  ⚠ 62 days ago    │
│  regex_parsing  │  █░░░░░░░ 18 │  ↓ down   │  ⚠ 41 days ago    │
└─────────────────┴──────────────┴───────────┴────────────────────┘

  ⚡ Skills to Revisit: sql_databases (62d), regex_parsing (41d)
  🧬 Coding Style: systematic  |  Most active: 11pm  |  Language: Python

  [dim] Note: Scores are statistical estimates for self-reflection only.
  Auto-formatters, squash commits, and conventional commit tools may
  affect readings. Calibration improves after 3+ scans. [/dim]
```
</details>

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=3" width="100%"/>

<br/>

## 🔬 The 10 Skill Disciplines

`atrophy` tracks your activity across 10 universal engineering skill areas. These work across any language and any codebase.

<table>
<thead>
<tr>
<th align="center">Icon</th>
<th align="left">Skill</th>
<th align="left">What It Tracks</th>
<th align="left">Example Signals</th>
</tr>
</thead>
<tbody>
<tr>
<td align="center">🧠</td>
<td><b>Algorithms</b></td>
<td>Data structures, sorting, recursion, dynamic programming</td>
<td>Tree traversals, binary search, memoization, heap usage</td>
</tr>
<tr>
<td align="center">🔍</td>
<td><b>Regex & Parsing</b></td>
<td>Pattern matching, text extraction, string manipulation</td>
<td>Capture groups, lookaheads, re.compile, named groups</td>
</tr>
<tr>
<td align="center">🗄️</td>
<td><b>SQL & Databases</b></td>
<td>Queries, schema design, optimization, transactions</td>
<td>Window functions, CTEs, raw cursor.execute, GROUP BY</td>
</tr>
<tr>
<td align="center">🌐</td>
<td><b>API Design</b></td>
<td>Route design, middleware, auth patterns, REST/GraphQL</td>
<td>Custom middleware, dependency injection, route handlers</td>
</tr>
<tr>
<td align="center">🛡️</td>
<td><b>Security</b></td>
<td>Auth, input validation, cryptography, permissions</td>
<td>Password hashing, JWT handling, parameterized queries</td>
</tr>
<tr>
<td align="center">⚡</td>
<td><b>Async & Concurrency</b></td>
<td>Async code, threads, event loops, parallel tasks</td>
<td>async/await, task groups, semaphores, goroutines</td>
</tr>
<tr>
<td align="center">✅</td>
<td><b>Testing</b></td>
<td>Unit tests, integration tests, mocks, property tests</td>
<td>Custom fixtures, deep mocking, pytest marks, hypothesis</td>
</tr>
<tr>
<td align="center">🏗️</td>
<td><b>Data Structures & OOP</b></td>
<td>Custom classes, type design, interfaces, generics</td>
<td>Dataclasses, custom trees/graphs, protocol classes</td>
</tr>
<tr>
<td align="center">💾</td>
<td><b>System I/O</b></td>
<td>File operations, networking, processes, sockets</td>
<td>pathlib, subprocess, socket programming, file streaming</td>
</tr>
<tr>
<td align="center">🔧</td>
<td><b>Tooling & DevOps</b></td>
<td>Build scripts, CI/CD, containers, automation</td>
<td>Docker multi-stage builds, GitHub Actions, bash pipelines</td>
</tr>
</tbody>
</table>

**How scores work:**
- Each skill is scored 0–100 based on how recently and how deeply you exercised it yourself
- Recent activity (last 30 days) counts 3× more than older activity
- A score below 8 or a gap of 45+ days marks a skill as a **"Skill to Revisit"**
- Scores update every time you run `atrophy scan`

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=3" width="100%"/>

<br/>

## 🔌 LLM Providers

atrophy works completely offline with no LLM. Add one to unlock personalized weekly challenges and smarter skill detection for less common languages.

<table>
<thead>
<tr>
<th align="center">Provider</th>
<th align="center">Privacy</th>
<th align="left">How to Set Up</th>
<th align="center">Best For</th>
<th align="center">Cost</th>
</tr>
</thead>
<tbody>
<tr>
<td align="center"><b>🦙 Ollama Local</b></td>
<td align="center">🔒 100% private<br/>nothing leaves machine</td>
<td><code>ollama serve</code><br/><code>ollama pull llama3.2</code></td>
<td align="center">Privacy-first teams<br/>offline use</td>
<td align="center">Free</td>
</tr>
<tr>
<td align="center"><b>☁️ Ollama Cloud</b></td>
<td align="center">☁️ Sent to ollama.com</td>
<td>API key from<br/><a href="https://ollama.com/settings/keys">ollama.com/settings/keys</a></td>
<td align="center">Large models without a GPU<br/>(70B, 671B etc.)</td>
<td align="center">Usage-based</td>
</tr>
<tr>
<td align="center"><b>🔵 OpenRouter</b></td>
<td align="center">☁️ Sent to provider</td>
<td>API key from<br/><a href="https://openrouter.ai/keys">openrouter.ai/keys</a></td>
<td align="center">Best value — 500+ models<br/>free options available</td>
<td align="center">Free tier + pay-per-use</td>
</tr>
<tr>
<td align="center"><b>🟡 OpenAI</b></td>
<td align="center">☁️ Sent to OpenAI</td>
<td>API key from<br/><a href="https://platform.openai.com">platform.openai.com</a></td>
<td align="center">Reliable, well-tested</td>
<td align="center">Pay per token</td>
</tr>
<tr>
<td align="center"><b>🟣 Anthropic</b></td>
<td align="center">☁️ Sent to Anthropic</td>
<td>API key from<br/><a href="https://console.anthropic.com">console.anthropic.com</a></td>
<td align="center">Best reasoning quality</td>
<td align="center">Pay per token</td>
</tr>
<tr>
<td align="center"><b>⬛ None (Offline)</b></td>
<td align="center">🔒 100% private<br/>no network at all</td>
<td>Skip during <code>atrophy init</code></td>
<td align="center">Full tracking + dashboard<br/>no challenges</td>
<td align="center">Free</td>
</tr>
</tbody>
</table>

> **Which provider should I pick?**
> - **Privacy first** → Ollama Local (free, fully offline, models run on your machine)
> - **Best free option** → OpenRouter (`qwen/qwq-32b:free` and `meta-llama/llama-3.3-70b-instruct:free` are excellent and free)
> - **Best quality** → Anthropic Claude Sonnet (most contextually accurate challenges)
> - **Corporate environment** → Ollama Local (your code never leaves your network)

**What data goes to the LLM?**
Only when generating challenges: a short, sanitized snippet of your own code (max 400 characters), your detected tech stack, and the skill category. Your full source files are never sent. You can run `atrophy` forever in tracking-only mode with no LLM at all.

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=3" width="100%"/>

<br/>

## 📋 All Commands

```bash
atrophy init                      # One-time setup for this repo
atrophy init --email you@dev.com  # Specify git author email manually

atrophy scan                      # Analyze last 180 days of commits
atrophy scan --days 90            # Analyze last 90 days only
atrophy scan --force              # Re-scan even if already done today

atrophy report                    # Full skill report in the terminal
atrophy report --json             # Output as JSON (for piping/scripts)
atrophy report --share            # Save report.md to current folder

atrophy dashboard                 # Launch interactive animated TUI

atrophy challenge                 # View this week's pending challenges
atrophy challenge --generate      # Generate 3 new personalized challenges
atrophy challenge --done 12       # Mark challenge #12 as complete

atrophy digest                    # Print weekly digest to terminal
atrophy digest --open             # Save and open in $EDITOR

atrophy share                     # Generate a shareable PNG card (for Twitter/X)
atrophy badge                     # Start a local server serving your score badge
atrophy config                    # Change LLM provider or settings
```

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=3" width="100%"/>

<br/>

## 📦 What Gets Stored and Where

`atrophy` stores everything in `~/.atrophy/` on your machine.

```
~/.atrophy/
├── atrophy.db        # SQLite database — all your scan history, skill scores, challenges
├── config.json       # Settings (provider choice, email, scan preferences)
├── .env              # API keys — never committed to git, never leaves your machine
└── digests/          # Weekly digest Markdown files
    ├── 2026-10.md
    └── 2026-11.md
```

**Nothing in your git repositories is ever modified.** `atrophy` is read-only. It reads commit metadata and diffs. It never writes, stages, or commits anything to any repo.

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=3" width="100%"/>

<br/>

## 🗺️ Roadmap

```
✅  v0.1  —  Core git scanner + 5-signal AI detection heuristics
✅  v0.2  —  Personal baseline calibration (no more penalizing good devs)
✅  v0.3  —  3-layer skill detection: Tree-sitter AST + LLM + keyword fallback
✅  v0.4  —  Animated Textual TUI dashboard
✅  v0.5  —  LLM challenge engine with real codebase context
✅  v0.6  —  OpenRouter (500+ models) + Ollama Cloud support
✅  v0.7  —  Wins system + positive momentum framing + weekly digests
🔄  v0.8  —  GitHub Action PR comments with skill reports    [in progress]
📅  v0.9  —  VS Code extension (live skill meter in status bar)
📅  v1.0  —  Team dashboards + multi-repo support
📅  v1.1  —  Mercurial backend support
```

> 💬 Have a feature idea? [Open a Discussion →](https://github.com/yourusername/atrophy/discussions)

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=3" width="100%"/>

<br/>

## ❓ FAQ

<details>
<summary><b>🔒 Does my code ever leave my machine?</b></summary>
<br>

**No, by default.** Everything `atrophy` does runs entirely on your local machine. Your git history, your diffs, your skill scores — all stored in `~/.atrophy/` and never sent anywhere.

The one exception is if you configure a cloud LLM provider (OpenAI, Anthropic, OpenRouter, or Ollama Cloud) for challenge generation. In that case, only a short, anonymized code snippet is sent — not your full source files. To keep everything 100% offline, use **Ollama Local** or skip the LLM entirely.
</details>

<details>
<summary><b>🤔 Can I use atrophy without any API key?</b></summary>
<br>

**Yes, completely.** `atrophy` works in full tracking mode with no API key at all. You get:
- ✅ Full git history scanning
- ✅ AI vs human classification (using the 5-signal heuristics)
- ✅ Skill health scores across all 10 disciplines
- ✅ The animated terminal dashboard
- ✅ Weekly digest exports
- ❌ AI-generated personalized challenges (requires a provider)

For challenges without any cloud service, install [Ollama](https://ollama.com) and pull any model — it runs locally, it's free, and your data stays on your machine.
</details>

<details>
<summary><b>🎯 How accurate is the AI detection?</b></summary>
<br>

`atrophy` uses 5 statistical signals combined with your personal baseline. In our testing it is reasonably accurate but not perfect — and that is by design.

A few things that can affect readings:
- **Squash commits** look like AI even when they're human (atrophy detects and marks these as "uncertain")
- **Auto-formatters** like ruff or black make your code look "too clean" — atrophy detects these tools in your repo and adjusts
- **Conventional commits** (`feat:`, `fix:`) are popular with AI tools but also with disciplined humans — atrophy checks your historical patterns before scoring this signal

The bottom line: treat your score as an honest personal mirror, not a precise measurement. It improves with more data — after 3+ scans, calibration accuracy increases significantly.
</details>

<details>
<summary><b>💼 Is it safe to use on my company's codebase?</b></summary>
<br>

Yes — with Ollama Local, `atrophy` is completely air-gapped. No data leaves your machine at any point. It only reads git metadata and diffs locally.

If you use a cloud LLM provider, only a small code snippet is sent for challenge generation. Consult your company's security policy if you are unsure about sending any code externally.

`atrophy` never uploads, indexes, or stores your code anywhere outside your own `~/.atrophy/` directory.
</details>

<details>
<summary><b>⚙️ Which languages and editors are supported?</b></summary>
<br>

`atrophy` works with **any git repository** — editor and IDE don't matter.

For skill detection, tree-sitter AST analysis supports: Python, TypeScript, JavaScript, Go, Rust, Java, Ruby, C, C++, and more. For unsupported languages, LLM semantic classification or keyword fallback handles detection automatically.

For version control, `atrophy` currently supports **git only**. Mercurial support is on the roadmap.
</details>

<details>
<summary><b>📅 How often should I run it?</b></summary>
<br>

**Once a week** gives you good signal with low noise. Running more often is fine — `atrophy scan` is fast (typically under 60 seconds) and it only processes new commits since the last scan.

For best results, scan weekly and do one challenge per week. After about 3 scans, `atrophy` has enough data to calibrate your personal baseline well and the scores become meaningfully accurate.
</details>

<details>
<summary><b>🏷️ How do I add the badge to my GitHub profile?</b></summary>
<br>

Run `atrophy badge` — it starts a local server at `http://localhost:6174` serving an SVG badge with your current human coding score. Add it to any README:

```markdown
![atrophy score](http://localhost:6174)
```

For a static shareable image, run `atrophy share` — it generates a `atrophy-card.png` in your current folder ready to post on Twitter/X.
</details>

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=3" width="100%"/>

<br/>

## 🤝 Contributing

<p align="center">
  <a href="https://github.com/yourusername/atrophy/pulls">
    <img src="https://img.shields.io/badge/PRs-Welcome!-9932CC?style=for-the-badge&logo=github&logoColor=white&labelColor=1a003a"/>
  </a>&nbsp;
  <a href="https://github.com/yourusername/atrophy/issues">
    <img src="https://img.shields.io/github/issues/yourusername/atrophy?style=for-the-badge&color=FF6B6B&logo=github&logoColor=white&labelColor=1a003a"/>
  </a>&nbsp;
  <a href="https://github.com/yourusername/atrophy/stargazers">
    <img src="https://img.shields.io/github/stars/yourusername/atrophy?style=for-the-badge&color=FFD700&logo=github&logoColor=white&labelColor=1a003a"/>
  </a>
</p>

`atrophy` is built to be easy to contribute to. The most impactful contributions:

- **Add a new skill category** — 5 steps, documented in `CONTRIBUTING.md`
- **Improve AST detection** — add node types to `SKILL_NODE_MAP` in `skill_mapper.py`
- **Add a new LLM provider** — copy `providers/base.py` pattern, 4 steps
- **Write tests** — every new feature needs a test in `tests/`

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

**Good first issues if you want somewhere to start:**
- Add Swift / Kotlin language support to tree-sitter skill detection
- Add `atrophy compare` command (compare two different time windows)
- Improve the Textual dashboard with Plotext charts
- Write a Homebrew formula for macOS one-line install

<br/>


<p align="center">
  <img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Hand%20gestures/Flexed%20Biceps.png" width="52"/>&nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Microscope.png" width="52"/>&nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Smilies/Alien%20Monster.png" width="52"/>
</p>

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:4B0082,50:8B00FF,100:B060FF&height=140&section=footer&text=Don't%20let%20your%20skills%20go%20quiet.&fontSize=26&fontColor=ffffff&animation=twinkling&fontAlignY=65" width="100%"/>
</p>

<p align="center">
  Built with 💜 by developers who refuse to lose their edge &nbsp;·&nbsp;
  <a href="https://pypi.org/p/atrophy">PyPI</a> &nbsp;·&nbsp;
  <a href="https://github.com/yourusername/atrophy">GitHub</a> &nbsp;·&nbsp;
  <a href="LICENSE">MIT License</a>
</p>
