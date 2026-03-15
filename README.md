# StudyFlow — NotebookLM × Notion Learning System

> An intelligent study system that bridges **NotebookLM** (knowledge synthesis) and **Notion** (structured, persistent notes) — orchestrated by Claude.

StudyFlow transforms the way CSE students learn. Upload any resource to NotebookLM — PDFs, YouTube lectures, web articles, research papers — and StudyFlow automatically structures the content into Cornell-style notes, spaced-repetition flashcards, Feynman explanations, and active recall quizzes inside Notion.

## Why This Pairing Is Powerful

| Tool | Role |
|------|------|
| **NotebookLM** | Synthesizes uploaded material into insights, Q&A, mind maps, quizzes |
| **Notion** | Permanent, structured, beautiful knowledge base with spaced repetition |
| **Claude** | Intelligent orchestrator bridging the two — via a `/studyflow` skill |

## Features

- 📝 **Structured Notes** — Cornell format with learning objectives, key definitions, code examples
- 🧠 **Spaced Repetition** — SM-2 algorithm flashcards (New → Learning → Review → Mastered)
- ❓ **Active Recall** — Auto-generated questions from every note
- 🧪 **Feynman Technique** — ELI5 explanations to surface knowledge gaps
- 📊 **Quiz Bank** — Import NotebookLM quizzes with score tracking
- 🎧 **Podcast Notes** — Extract key insights from NotebookLM Deep Dive audio
- 🗺️ **Mind Map Import** — Convert mind maps to Notion page hierarchies
- 📅 **Exam Prep Mode** — Calculates daily review targets before exams
- 🔍 **Multi-Source Finder** — Search YouTube + Web + arXiv in parallel, add sources to notebooks
- 🤖 **MCP Server** — 9 Claude Desktop tools for source management

## Architecture

```
/studyflow <command> <notebook> [options]
      │
      ├── notebooklm CLI ──── query, generate artifacts, extract quizzes/mind maps
      │
      ├── Notion MCP ───────── create pages, databases, update flashcard intervals
      │
      └── MCP Server ──────── 9 tools for source discovery and ingestion
                              (Claude Desktop integration)
```

## Quick Start

See [docs/SETUP.md](docs/SETUP.md) for full setup instructions.

## Commands

| Command | Description |
|---------|-------------|
| `/studyflow setup` | Create the full Notion workspace (one-time) |
| `/studyflow notes <nb> [--topic T]` | Generate structured notes |
| `/studyflow flashcards <nb>` | Generate SM-2 flashcards |
| `/studyflow review` | Process today's due cards |
| `/studyflow quiz <nb>` | Import NotebookLM quiz |
| `/studyflow feynman <nb> --topic T` | Generate Feynman explanation |
| `/studyflow study <nb>` | Full study session |
| `/studyflow exam <course> --days N` | Exam prep mode |
| `/studyflow brief` | Daily study brief |
| `/studyflow find-sources <topic>` | Search YouTube + Web + arXiv |
| `/studyflow add <nb> <url>` | Add source to notebook |

## Target User

CSE undergrad studying AI, Compilers, Theory of Computing, IoT, DSA, OS, Computer Architecture — also freelancing and self-learning new tech stacks.

## License

MIT
