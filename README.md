# StudyFlow — NotebookLM × Notion Learning System

> An intelligent study system that bridges **NotebookLM** (knowledge synthesis) and **Notion** (structured, persistent notes) — orchestrated by Claude.

StudyFlow transforms the way CSE students learn. Upload any resource to NotebookLM — PDFs, YouTube lectures, web articles, research papers — and StudyFlow automatically structures the content into Cornell-style notes, spaced-repetition flashcards, Feynman explanations, and active recall quizzes inside Notion.

## Why This Pairing Is Powerful

| Tool | Role |
|------|------|
| **NotebookLM** | Synthesizes uploaded material into insights, Q&A, mind maps, quizzes, podcasts |
| **Notion** | Permanent, structured, beautiful knowledge base with spaced repetition |
| **Claude** | Intelligent orchestrator bridging the two — via a `/studyflow` skill and 9 Claude Desktop tools |

The result is a system better than any single tool: NotebookLM is excellent at synthesizing uploaded material; Notion is excellent at structured, persistent, linked knowledge bases; Claude is the intelligent glue.

## Features

- 📝 **Structured Notes** — Cornell format with learning objectives, key definitions, code examples, Feynman explanations
- 🧠 **SM-2 Spaced Repetition** — Flashcards with `Ease Factor × Interval` scheduling (New → Learning → Review → Mastered)
- 🔍 **Active Recall** — 5–8 auto-generated questions on every note page
- 🧪 **Feynman Technique** — ELI12 explanations that surface knowledge gaps
- ❓ **Quiz Bank** — Import NotebookLM quizzes with accuracy tracking
- 🎧 **Podcast Notes** — Extract key insights from NotebookLM Deep Dive audio
- 🗺️ **Mind Map Import** — Convert mind maps to Notion page hierarchies
- 📅 **Exam Prep Mode** — Calculates daily review targets, crunch schedules
- 🔍 **Multi-Source Finder** — Search YouTube + DuckDuckGo + arXiv in parallel, no API keys
- 🤖 **9 Claude Desktop MCP Tools** — Source discovery and notebook management

## Architecture

```
/studyflow <command> <notebook> [options]
      │
      ├── notebooklm CLI ──── query, generate artifacts, extract quizzes/mind maps/podcasts
      │
      ├── Notion MCP ───────── create pages, databases, update SM-2 flashcard intervals
      │
      └── studyflow_mcp_server.py ── 9 Claude Desktop tools for source ingestion
                                     (YouTube transcripts, web scraping, arXiv, DuckDuckGo)
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install yt-dlp

# 2. Register MCP server with Claude Desktop
# See docs/claude-desktop-setup.md

# 3. Copy SKILL.md to Claude Code skills directory
cp SKILL.md ~/.claude/skills/studyflow/SKILL.md

# 4. Create Notion workspace
# In Claude Code:
/studyflow setup

# 5. Start studying
/studyflow notes "Your Notebook Name" --topic "Dynamic Programming"
```

See [docs/SETUP.md](docs/SETUP.md) for complete installation instructions.

## Claude Code Commands

| Command | Description |
|---------|-------------|
| `/studyflow setup` | Create Notion workspace (one-time) |
| `/studyflow notes <nb> [--topic T] [--type concept\|algo\|tech]` | Generate structured notes |
| `/studyflow flashcards <nb> [--count N] [--cloze]` | Generate SM-2 flashcards |
| `/studyflow review` | Process today's due cards (SM-2) |
| `/studyflow quiz <nb>` | Import NotebookLM quiz into Quiz Bank |
| `/studyflow feynman <nb> --topic T` | Generate Feynman explanation |
| `/studyflow study <nb>` | Full study session (notes + cards + quiz) |
| `/studyflow exam <course> --days N` | Exam prep mode |
| `/studyflow brief` | Daily study brief |
| `/studyflow search-youtube <query> [--filter lecture\|tutorial\|short]` | Find YouTube videos |
| `/studyflow add <nb> <url>` | Add source to notebook |
| `/studyflow podcast <nb>` | Extract podcast key insights |
| `/studyflow mindmap <nb>` | Import mind map as page hierarchy |
| `/studyflow slides <nb>` | Import slide deck summaries |
| `/studyflow project <name>` | Create project + curriculum links |
| `/studyflow sync <nb>` | Re-sync updated notebook |

## Claude Desktop MCP Tools

| Tool | Description |
|------|-------------|
| `studyflow_list_notebooks` | List all NotebookLM notebooks |
| `studyflow_find_sources` | Search YouTube + Web + arXiv in parallel |
| `studyflow_search_youtube` | YouTube search with lecture/tutorial/short filter modes |
| `studyflow_add_youtube` | Extract VTT transcript → upload to NotebookLM |
| `studyflow_add_web` | Site-specific scraping → upload to NotebookLM |
| `studyflow_add_url` | Add URL directly to NotebookLM |
| `studyflow_add_research` | NotebookLM web research (fast/deep mode) |
| `studyflow_ask` | Query a notebook with a question |
| `studyflow_source_list` | List sources in a notebook |

## Notion Workspace Structure

```
📚 StudyFlow
├── 📈 Dashboard           (command reference, daily stats)
├── 🗂️ Courses             (one sub-page per notebook/course)
├── 🔧 Projects & Freelance
├── 📚 Knowledge Base      (all notes database)
├── 🃏 Flashcard Vault     (SM-2 flashcards database)
├── ❓ Quiz Bank           (imported quizzes database)
└── 📅 Study Sessions      (session log database)
```

## SM-2 Algorithm

StudyFlow implements the classic SM-2 spaced repetition algorithm:

```
Again: interval=1, repetitions=0
Hard:  interval=max(1, round(interval × 1.2)), ease_factor=max(1.3, ef - 0.15)
Easy:  interval = 1 | 6 | round(interval × ease_factor)  [based on repetition count]
       ease_factor = min(4.0, ease_factor + 0.1)

Status: reps=0 → 🆕 New | 1-2 → 📖 Learning | 3-5 → 🔄 Review | 6+ & interval>21 → ✅ Mastered
```

## Target User

CSE undergrad studying AI, Compilers, Theory of Computing, IoT, DSA, OS, Computer Architecture — also freelancing and self-learning new tech stacks on the job.

## Requirements

- Python 3.11+
- [notebooklm CLI](https://pypi.org/project/notebooklm/) — authenticated (`notebooklm login`)
- Claude Code with Notion MCP configured
- yt-dlp (optional — for YouTube transcript extraction)

## File Structure

```
studyflow/
├── studyflow_mcp_server.py      # Claude Desktop MCP server (9 tools)
├── SKILL.md                     # Claude Code skill definition (16 commands)
├── requirements.txt             # Python dependencies
├── docs/
│   ├── SETUP.md                 # Full installation guide
│   ├── claude-desktop-setup.md  # MCP server registration
│   └── notion-schema.md         # Database property schemas
└── examples/
    └── claude_desktop_config.example.json
```

## License

MIT
