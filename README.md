<div align="center">

<img src="https://capsule-render.vercel.app/api?type=venom&height=340&text=ATROPHY&fontSize=130&color=0:8B00FF,50:9932CC,100:4B0082&fontColor=ffffff&stroke=9932CC&strokeWidth=3&animation=fadeIn&desc=Your%20coding%20skills%20have%20a%20half-life.%20atrophy%20measures%20it.&descSize=20&descAlignY=78&fontAlignY=45" width="100%"/>

<br/>

<!-- BADGES ROW 1 -->
<a href="https://pypi.org/project/atrophy/"><img src="https://img.shields.io/badge/PyPI-v0.1.0-8B00FF?style=for-the-badge&logo=pypi&logoColor=white&labelColor=12001f" alt="PyPI"/></a>&nbsp;
<a href="https://pypi.org/project/atrophy/"><img src="https://img.shields.io/badge/pip%20install-atrophy-9932CC?style=for-the-badge&logo=python&logoColor=white&labelColor=12001f"/></a>&nbsp;
<img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white&labelColor=12001f"/>&nbsp;
<img src="https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge&logo=opensourceinitiative&logoColor=white&labelColor=12001f"/>

<br/><br/>

<!-- BADGES ROW 2 -->
<img src="https://img.shields.io/badge/Powered%20by-uv-DE5FE9?style=for-the-badge&logoColor=white&labelColor=12001f"/>&nbsp;
<img src="https://img.shields.io/badge/AST-Tree--sitter-FF6B6B?style=for-the-badge&labelColor=12001f"/>&nbsp;
<img src="https://img.shields.io/badge/TUI-Textual-9932CC?style=for-the-badge&labelColor=12001f"/>&nbsp;
<img src="https://img.shields.io/badge/Storage-SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white&labelColor=12001f"/>&nbsp;
<img src="https://img.shields.io/badge/100%25-Local%20by%20Default-22C55E?style=for-the-badge&labelColor=12001f"/>

<br/><br/>

<!-- NAV LINKS -->
<a href="#-the-problem-nobody-talks-about">🚨 Problem</a> &nbsp;·&nbsp;
<a href="#-what-atrophy-does">💡 What It Does</a> &nbsp;·&nbsp;
<a href="#-how-it-works">⚙️ How It Works</a> &nbsp;·&nbsp;
<a href="#-installation">🚀 Install</a> &nbsp;·&nbsp;
<a href="#-quickstart-2-minutes">⚡ Quickstart</a> &nbsp;·&nbsp;
<a href="#-the-10-skill-disciplines">🔬 Skills</a> &nbsp;·&nbsp;
<a href="#-llm-providers">🔌 Providers</a> &nbsp;·&nbsp;
<a href="#-faq">❓ FAQ</a>

</div>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=4" width="100%"/>

<br/>

## 🚨 The Problem Nobody Talks About

<img align="right" width="165" src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Smilies/Anxious%20Face%20with%20Sweat.png"/>

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

**That is what `atrophy` is for.**

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=4" width="100%"/>

<br/>

## 💡 What atrophy Does

<img align="left" width="155" src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Smilies/Alien%20Monster.png"/>

&nbsp;&nbsp; `atrophy` connects to your local git history and does **four things**:

&nbsp;&nbsp; **1. Measures what YOU actually wrote** — using statistical signals, it separates commits you personally wrote from AI-generated ones.

&nbsp;&nbsp; **2. Maps your skill health** — tracks 10 engineering disciplines and scores how actively you exercise each one yourself.

&nbsp;&nbsp; **3. Shows you the decay** — a beautiful terminal dashboard reveals which skills are going dark and how fast, with a month-by-month timeline.

&nbsp;&nbsp; **4. Fights back for you** — every week, 3 personalized coding challenges targeting your dead zones, using real patterns from your own codebase.

<br clear="left"/>

<div align="center">

```
╔══════════════════════════════════════════════════════════════════╗
║  🔒  100% LOCAL  ·  Your code NEVER leaves your machine         ║
║      Read-only · No uploads · No telemetry · No phone home      ║
╚══════════════════════════════════════════════════════════════════╝
```

</div>

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=4" width="100%"/>

<br/>

## ⚙️ How It Works

<br/>

<div align="center">

```
   YOUR GIT REPO                                          YOUR TERMINAL
  ┌─────────────┐                                        ┌─────────────────────┐
  │ commit log  │──── atrophy scan ────────────────────▶ │  Skill Health: 85   │
  │ diff hunks  │                                        │  Dead Zones: sql    │
  │ timestamps  │──── 5-signal AI detection ───────────▶ │  Challenges: 3 new  │
  │ messages    │                                        │  Trend: ↑ improving │
  └─────────────┘                                        └─────────────────────┘
        │
        ▼
  ┌───────────────────────────────────────────┐
  │  ~/.atrophy/atrophy.db  (stays local)     │
  └───────────────────────────────────────────┘
```

</div>

<br/>

### 🔍 Step 1 — Reading Your Git History

`atrophy scan` walks your entire commit history for the past 180 days. It reads the actual diff of each commit and **automatically filters out noise**: dependency lock files, auto-generated code, minified files, and merge commits.

---

### 🤖 Step 2 — Separating Human from AI Commits

This is the statistical heart of `atrophy`. **5 signals** combine into a single probability score per commit:

<br/>

<div align="center">

<table>
<thead>
<tr>
<th align="center">Signal</th>
<th align="left">What It Measures</th>
<th align="left">The Insight</th>
<th align="center">Weight</th>
</tr>
</thead>
<tbody>
<tr>
<td align="center">⚡<br/><b>Velocity</b></td>
<td>Lines added per minute vs your personal average</td>
<td>AI pastes 200 lines in 8 seconds. Humans type.</td>
<td align="center"><code>HIGH</code></td>
</tr>
<tr>
<td align="center">〰️<br/><b>Burstiness</b></td>
<td>Uniformity of line lengths in the diff</td>
<td>AI code is suspiciously uniform. Human code is messy.</td>
<td align="center"><code>HIGH</code></td>
</tr>
<tr>
<td align="center">🔬<br/><b>Entropy</b></td>
<td>Character distribution patterns in code</td>
<td>AI produces "expected" code. Humans are quirky.</td>
<td align="center"><code>MED</code></td>
</tr>
<tr>
<td align="center">🎨<br/><b>Formatter</b></td>
<td>Whether formatting is machine-perfect</td>
<td>Running ruff/black yourself? atrophy detects & adjusts.</td>
<td align="center"><code>MED</code></td>
</tr>
<tr>
<td align="center">💬<br/><b>Msg Depth</b></td>
<td>Commit message patterns & specificity</td>
<td><code>"fix"</code> at 2am = you. <code>"feat: add JWT middleware"</code> at 2am = Cursor.</td>
<td align="center"><code>MED</code></td>
</tr>
</tbody>
</table>

</div>

<br/>

> 🎯 **Personal Baseline:** atrophy calibrates all signals to *your* natural pace — from your oldest commits, before heavy AI use. A fast typist who uses conventional commits won't be falsely flagged.

---

### 🧬 Step 3 — Skill Detection (3 Layers)

<br/>

<div align="center">

<table>
<thead>
<tr>
<th align="center">Priority</th>
<th align="left">Layer</th>
<th align="left">How It Works</th>
<th align="left">Languages</th>
</tr>
</thead>
<tbody>
<tr>
<td align="center"><code>1st</code><br/>✅ <b>Best</b></td>
<td><b>Tree-sitter AST</b></td>
<td>Real code parser — same tech as VS Code syntax highlighting. Counts actual AST nodes: async functions, SQL calls, test assertions, custom classes.</td>
<td>Python · TS · JS · Go · Rust · Java · Ruby · C++ · more</td>
</tr>
<tr>
<td align="center"><code>2nd</code><br/>🧠 <b>Smart</b></td>
<td><b>LLM Semantic</b></td>
<td>For ambiguous or rare languages, sends a short anonymized snippet to your configured LLM. Your API key. Direct to provider. No middleman.</td>
<td>Any language · complex cases</td>
</tr>
<tr>
<td align="center"><code>3rd</code><br/>⚡ <b>Free</b></td>
<td><b>Keyword Fallback</b></td>
<td>Smart keyword scanning inside actual code only — not comments or strings — using language-specific comment strippers.</td>
<td>Any language · zero cost · always available</td>
</tr>
</tbody>
</table>

</div>

---

### 🏆 Step 4 — Personalized Weekly Challenges

Every week, `atrophy challenge --generate` picks your top 3 dead zones and creates targeted exercises using context from **your actual codebase**:

<div align="center">

| Context Sent to LLM | Example Output |
|---------------------|----------------|
| Most-committed files (names only) | *"Add a raw aggregate query to your existing `User` model"* |
| Short code sample you personally wrote | *"Using the patterns already in `repositories/user_repo.py`"* |
| Detected tech stack & frameworks | *"With your SQLAlchemy setup, not a generic ORM tutorial"* |
| Primary language | Not LeetCode. Not generic tutorials. **Your stack.** |

</div>

> 🛡️ If the LLM returns something generic or hallucinated, atrophy auto-detects it and swaps in a hand-crafted fallback challenge. You always get something useful.

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=4" width="100%"/>

<br/>

## 🚀 Installation

<img align="right" width="120" src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Rocket.png"/>

**Recommended — [`uv`](https://github.com/astral-sh/uv)** *(Rust-powered, 100× faster than pip, keeps atrophy isolated)*

```bash
# Install uv first (if you don't have it)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install atrophy globally
uv tool install atrophy

# Verify
atrophy --version
```

**Or plain pip:**
```bash
pip install atrophy
```

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=4" width="100%"/>

<br/>

## ⚡ Quickstart (2 Minutes)

```bash
# ① Go to any project with git history
cd your-project

# ② One-time setup — connects atrophy to this repo
#    Asks for your git email + optionally an LLM provider
atrophy init

# ③ Scan the last 180 days (takes 10–60s depending on repo size)
atrophy scan

# ④ Read your full skill report in the terminal
atrophy report

# ⑤ Launch the interactive animated dashboard
atrophy dashboard

# ⑥ Generate this week's personalized skill challenges
atrophy challenge --generate

# ⑦ Export your weekly digest to Markdown
atrophy digest --open
```

<br/>

<details>
<summary><b>📊 &nbsp; Preview: <code>atrophy report</code></b></summary>
<br/>

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
│  sql_databases  │  ██░░░░░░ 29 │  ↓ down   │  ⚠  62 days ago   │
│  regex_parsing  │  █░░░░░░░ 18 │  ↓ down   │  ⚠  41 days ago   │
└─────────────────┴──────────────┴───────────┴────────────────────┘

  ⚡ Skills to Revisit: sql_databases (62d), regex_parsing (41d)
  🧬 Coding Style: systematic  |  Most active: 11pm  |  Language: Python
```

</details>

<details>
<summary><b>🖥️ &nbsp; Preview: <code>atrophy dashboard</code></b></summary>
<br/>

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
║  🔥 Streak: 3 weeks  |  Pending: 2 challenges  |  [Q]uit  [R]efresh   ║
╚══════════════════════════════════════════════════════════════════════════╝
```

</details>

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=4" width="100%"/>

<br/>

## 🔬 The 10 Skill Disciplines

`atrophy` tracks **10 universal engineering skill areas** — across any language and any codebase.

<br/>

<div align="center">

<table>
<thead>
<tr>
<th align="center" width="60">Icon</th>
<th align="left" width="200">Skill</th>
<th align="left">What It Tracks</th>
<th align="left">Example Signals</th>
</tr>
</thead>
<tbody>
<tr>
<td align="center">🧠</td>
<td><b>Algorithms</b></td>
<td>Data structures, sorting, recursion, dynamic programming</td>
<td><code>tree traversals</code> · <code>binary search</code> · <code>memoization</code> · <code>heap usage</code></td>
</tr>
<tr>
<td align="center">🔍</td>
<td><b>Regex & Parsing</b></td>
<td>Pattern matching, text extraction, string manipulation</td>
<td><code>capture groups</code> · <code>lookaheads</code> · <code>re.compile</code> · <code>named groups</code></td>
</tr>
<tr>
<td align="center">🗄️</td>
<td><b>SQL & Databases</b></td>
<td>Queries, schema design, optimization, transactions</td>
<td><code>window functions</code> · <code>CTEs</code> · <code>cursor.execute</code> · <code>GROUP BY</code></td>
</tr>
<tr>
<td align="center">🌐</td>
<td><b>API Design</b></td>
<td>Route design, middleware, auth patterns, REST/GraphQL</td>
<td><code>middleware</code> · <code>dependency injection</code> · <code>route handlers</code></td>
</tr>
<tr>
<td align="center">🛡️</td>
<td><b>Security</b></td>
<td>Auth, input validation, cryptography, permissions</td>
<td><code>password hashing</code> · <code>JWT handling</code> · <code>parameterized queries</code></td>
</tr>
<tr>
<td align="center">⚡</td>
<td><b>Async & Concurrency</b></td>
<td>Async code, threads, event loops, parallel tasks</td>
<td><code>async/await</code> · <code>task groups</code> · <code>semaphores</code> · <code>goroutines</code></td>
</tr>
<tr>
<td align="center">✅</td>
<td><b>Testing</b></td>
<td>Unit tests, integration tests, mocks, property tests</td>
<td><code>fixtures</code> · <code>deep mocking</code> · <code>pytest marks</code> · <code>hypothesis</code></td>
</tr>
<tr>
<td align="center">🏗️</td>
<td><b>Data Structures & OOP</b></td>
<td>Custom classes, type design, interfaces, generics</td>
<td><code>dataclasses</code> · <code>custom trees/graphs</code> · <code>protocol classes</code></td>
</tr>
<tr>
<td align="center">💾</td>
<td><b>System I/O</b></td>
<td>File operations, networking, processes, sockets</td>
<td><code>pathlib</code> · <code>subprocess</code> · <code>socket programming</code></td>
</tr>
<tr>
<td align="center">🔧</td>
<td><b>Tooling & DevOps</b></td>
<td>Build scripts, CI/CD, containers, automation</td>
<td><code>multi-stage builds</code> · <code>GitHub Actions</code> · <code>bash pipelines</code></td>
</tr>
</tbody>
</table>

</div>

<br/>

<div align="center">

**How Scores Work**

```
  0 ──────────── 8 ────────────────── 50 ──────────────────── 100
  │              │                    │                        │
  │   DEAD ZONE  │     FADING  ↓      │     HEALTHY  ↑         │
  │  ⚠ Revisit  │   Needs attention  │    Keep it up!         │

  • Score < 8 or gap > 45 days  →  flagged as ⚠ Skill to Revisit
  • Last 30 days of activity    →  counts 3× more than older work
  • Scores update on every      →  atrophy scan
```

</div>

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=4" width="100%"/>

<br/>

## 🔌 LLM Providers

`atrophy` works **completely offline** with no LLM. Add one to unlock personalized weekly challenges and smarter skill detection for less common languages.

<br/>

<div align="center">

<table>
<thead>
<tr>
<th align="center">Provider</th>
<th align="center">Privacy</th>
<th align="left">Setup</th>
<th align="left">Best For</th>
<th align="center">Cost</th>
</tr>
</thead>
<tbody>
<tr>
<td align="center"><b>🦙 Ollama Local</b></td>
<td align="center">🟢 100% private<br/><sub>nothing leaves machine</sub></td>
<td><code>ollama serve</code><br/><code>ollama pull llama3.2</code></td>
<td>Privacy-first · fully offline · corporate use</td>
<td align="center"><b>Free</b></td>
</tr>
<tr>
<td align="center"><b>🔵 OpenRouter</b></td>
<td align="center">🔵 Cloud<br/><sub>sent to provider</sub></td>
<td><a href="https://openrouter.ai/keys">openrouter.ai/keys</a></td>
<td>Best value — 500+ models, free options available</td>
<td align="center"><b>Free tier</b><br/><sub>+ pay-per-use</sub></td>
</tr>
<tr>
<td align="center"><b>🟣 Anthropic</b></td>
<td align="center">🔵 Cloud<br/><sub>sent to Anthropic</sub></td>
<td><a href="https://console.anthropic.com">console.anthropic.com</a></td>
<td>Best reasoning quality · most accurate challenges</td>
<td align="center"><sub>Pay per token</sub></td>
</tr>
<tr>
<td align="center"><b>🟡 OpenAI</b></td>
<td align="center">🔵 Cloud<br/><sub>sent to OpenAI</sub></td>
<td><a href="https://platform.openai.com">platform.openai.com</a></td>
<td>Reliable · well-tested</td>
<td align="center"><sub>Pay per token</sub></td>
</tr>
<tr>
<td align="center"><b>☁️ Ollama Cloud</b></td>
<td align="center">🔵 Cloud<br/><sub>sent to ollama.com</sub></td>
<td><a href="https://ollama.com/settings/keys">ollama.com/settings/keys</a></td>
<td>Huge models without a GPU (70B, 671B)</td>
<td align="center"><sub>Usage-based</sub></td>
</tr>
<tr>
<td align="center"><b>⬛ None (Offline)</b></td>
<td align="center">🟢 Air-gapped<br/><sub>zero network</sub></td>
<td>Skip during <code>atrophy init</code></td>
<td>Full tracking + dashboard · no AI challenges</td>
<td align="center"><b>Free</b></td>
</tr>
</tbody>
</table>

</div>

<br/>

> **💡 Which should I pick?**
>
> | Goal | Pick |
> |------|------|
> | 🔒 Maximum privacy | **Ollama Local** — free, fully offline |
> | 💸 Best free option | **OpenRouter** — `qwen/qwq-32b:free` and `meta-llama/llama-3.3-70b-instruct:free` are excellent |
> | 🧠 Best quality | **Anthropic Claude Sonnet** — most contextually accurate challenges |
> | 🏢 Corporate environment | **Ollama Local** — your code never leaves your network |

**What data goes to the LLM?** Only a short, sanitized snippet of your own code (max 400 chars), your detected tech stack, and the skill category. Your full source files are **never** sent.

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=4" width="100%"/>

<br/>

## 📋 All Commands

```bash
# ── Setup ────────────────────────────────────────────────────────────────
atrophy init                       # One-time setup for this repo
atrophy init --email you@dev.com   # Specify git author email manually

# ── Scanning ─────────────────────────────────────────────────────────────
atrophy scan                       # Analyze last 180 days of commits
atrophy scan --days 90             # Analyze last 90 days only
atrophy scan --force               # Re-scan even if already done today

# ── Reporting ────────────────────────────────────────────────────────────
atrophy report                     # Full skill report in the terminal
atrophy report --json              # Output as JSON (for piping/scripts)
atrophy report --share             # Save report.md to current folder

# ── Dashboard ────────────────────────────────────────────────────────────
atrophy dashboard                  # Launch interactive animated TUI

# ── Challenges ───────────────────────────────────────────────────────────
atrophy challenge                  # View this week's pending challenges
atrophy challenge --generate       # Generate 3 new personalized challenges
atrophy challenge --done 12        # Mark challenge #12 as complete

# ── Sharing ──────────────────────────────────────────────────────────────
atrophy digest                     # Print weekly digest to terminal
atrophy digest --open              # Save and open in $EDITOR
atrophy share                      # Generate a shareable PNG card
atrophy badge                      # Start local server serving your badge SVG

# ── Config ───────────────────────────────────────────────────────────────
atrophy config                     # Change LLM provider or settings
```

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=4" width="100%"/>

<br/>

## 📦 What Gets Stored and Where

`atrophy` stores everything in `~/.atrophy/` — **nothing** in your git repositories is ever modified.

```
~/.atrophy/
├── atrophy.db        # SQLite — all scan history, skill scores, challenges
├── config.json       # Settings (provider choice, email, scan preferences)
├── .env              # API keys — never committed, never leaves your machine
└── digests/
    ├── 2026-10.md    # Weekly digest exports
    └── 2026-11.md
```

<div align="center">

| What atrophy ✅ DOES | What atrophy ❌ NEVER DOES |
|:-------------------:|:------------------------:|
| Reads commit metadata | Write to your repo |
| Reads diff content locally | Upload your code |
| Stores scores in `~/.atrophy/` | Send telemetry |
| Generates local reports | Phone home |

</div>

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=4" width="100%"/>

<br/>

## 🗺️ Roadmap

<br/>

<div align="center">

| Status | Version | Feature |
|:------:|:-------:|---------|
| ✅ Done | `v0.1` | Core git scanner + 5-signal AI detection heuristics |
| ✅ Done | `v0.2` | Personal baseline calibration (no more penalizing good devs) |
| ✅ Done | `v0.3` | 3-layer skill detection: Tree-sitter AST + LLM + keyword fallback |
| ✅ Done | `v0.4` | Animated Textual TUI dashboard |
| ✅ Done | `v0.5` | LLM challenge engine with real codebase context |
| ✅ Done | `v0.6` | OpenRouter (500+ models) + Ollama Cloud support |
| ✅ Done | `v0.7` | Wins system + positive momentum framing + weekly digests |
| 🔄 Active | `v0.8` | **GitHub Action PR comments with skill reports** |
| 📅 Planned | `v0.9` | VS Code extension — live skill meter in status bar |
| 📅 Planned | `v1.0` | Team dashboards + multi-repo support |
| 📅 Planned | `v1.1` | Mercurial backend support |

</div>

<br/>

> 💬 Have a feature idea? [**Open a Discussion →**](https://github.com/kvcops/Atrophy/discussions)

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=4" width="100%"/>

<br/>

## ❓ FAQ

<details>
<summary><b>🔒 &nbsp; Does my code ever leave my machine?</b></summary>
<br/>

**No, by default.** Everything `atrophy` does runs entirely on your local machine. Your git history, your diffs, your skill scores — all stored in `~/.atrophy/` and never sent anywhere.

The one exception is if you configure a cloud LLM provider for challenge generation. In that case, **only a short, anonymized code snippet is sent** — not your full source files. To keep everything 100% offline, use **Ollama Local** or skip the LLM entirely.
</details>

<details>
<summary><b>🤔 &nbsp; Can I use atrophy without any API key?</b></summary>
<br/>

**Yes, completely.** `atrophy` works in full tracking mode with no API key at all. You get:

- ✅ Full git history scanning
- ✅ AI vs human classification (5-signal heuristics)
- ✅ Skill health scores across all 10 disciplines
- ✅ The animated terminal dashboard
- ✅ Weekly digest exports
- ❌ AI-generated personalized challenges *(requires a provider)*

For offline challenges, install [Ollama](https://ollama.com) and pull any model — free, local, private.
</details>

<details>
<summary><b>🎯 &nbsp; How accurate is the AI detection?</b></summary>
<br/>

`atrophy` uses 5 statistical signals combined with your personal baseline. It is reasonably accurate but not perfect — and that is by design.

Things that can affect readings:
- **Squash commits** look like AI even when they're human → marked as *"uncertain"*
- **Auto-formatters** like ruff or black make code look "too clean" → atrophy detects and adjusts
- **Conventional commits** are popular with both AI and disciplined humans → atrophy checks your historical patterns

Treat your score as an **honest personal mirror**, not a verdict. Accuracy improves significantly after 3+ scans.
</details>

<details>
<summary><b>💼 &nbsp; Is it safe to use on my company's codebase?</b></summary>
<br/>

Yes — with **Ollama Local**, `atrophy` is completely air-gapped. No data leaves your machine at any point. It only reads git metadata and diffs locally.

`atrophy` never uploads, indexes, or stores your code anywhere outside your own `~/.atrophy/` directory.
</details>

<details>
<summary><b>⚙️ &nbsp; Which languages and editors are supported?</b></summary>
<br/>

`atrophy` works with **any git repository** — editor and IDE don't matter.

Tree-sitter AST analysis supports: Python, TypeScript, JavaScript, Go, Rust, Java, Ruby, C, C++, and more. For unsupported languages, LLM semantic classification or keyword fallback handles detection automatically.

Currently supports **git only**. Mercurial support is on the roadmap.
</details>

<details>
<summary><b>📅 &nbsp; How often should I run it?</b></summary>
<br/>

**Once a week** gives you good signal with low noise. `atrophy scan` is fast — typically under 60 seconds — and only processes new commits since the last scan.

After about **3 scans**, atrophy has enough data to calibrate your personal baseline and scores become meaningfully accurate.
</details>

<details>
<summary><b>🏷️ &nbsp; How do I add the badge to my GitHub profile?</b></summary>
<br/>

Run `atrophy badge` — it starts a local server at `http://localhost:6174` serving an SVG badge:

```markdown
![atrophy score](http://localhost:6174)
```

For a static image, run `atrophy share` — it generates `atrophy-card.png` ready to post anywhere.
</details>

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=gradient&customColorList=24,20,15,12&height=4" width="100%"/>

<br/>

## 🤝 Contributing

<div align="center">

<a href="https://github.com/kvcops/Atrophy/pulls">
  <img src="https://img.shields.io/badge/PRs-Welcome!-9932CC?style=for-the-badge&logo=github&logoColor=white&labelColor=1a003a"/>
</a>&nbsp;
<a href="https://github.com/kvcops/Atrophy/issues">
  <img src="https://img.shields.io/github/issues/kvcops/Atrophy?style=for-the-badge&color=FF6B6B&logo=github&logoColor=white&labelColor=1a003a"/>
</a>&nbsp;
<a href="https://github.com/kvcops/Atrophy/stargazers">
  <img src="https://img.shields.io/github/stars/kvcops/Atrophy?style=for-the-badge&color=FFD700&logo=github&logoColor=white&labelColor=1a003a"/>
</a>

</div>

<br/>

<div align="center">

| Area | What To Do | Where |
|------|-----------|-------|
| 🆕 New skill category | 5 steps, fully documented | `CONTRIBUTING.md` |
| 🔍 Better AST detection | Add node types | `skill_mapper.py` → `SKILL_NODE_MAP` |
| 🔌 New LLM provider | Copy base pattern, 4 steps | `providers/base.py` |
| 🧪 Tests | Every new feature needs coverage | `tests/` |

</div>

<br/>

**Good first issues:**
- Add Swift / Kotlin language support to tree-sitter skill detection
- Add `atrophy compare` command (compare two different time windows)
- Improve the Textual dashboard with Plotext charts
- Write a Homebrew formula for macOS one-line install

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

<br/>

<div align="center">
  <img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Hand%20gestures/Flexed%20Biceps.png" width="55"/>&nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Objects/Microscope.png" width="55"/>&nbsp;&nbsp;
  <img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Smilies/Alien%20Monster.png" width="55"/>
</div>

<br/>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:4B0082,50:8B00FF,100:B060FF&height=160&section=footer&text=Don't%20let%20your%20skills%20go%20quiet.&fontSize=28&fontColor=ffffff&animation=twinkling&fontAlignY=65" width="100%"/>

<div align="center">

Built with 💜 by developers who refuse to lose their edge

[PyPI](https://pypi.org/project/atrophy/) &nbsp;·&nbsp; [GitHub](https://github.com/kvcops/Atrophy) &nbsp;·&nbsp; [Discussions](https://github.com/kvcops/Atrophy/discussions) &nbsp;·&nbsp; [MIT License](LICENSE)

</div>
