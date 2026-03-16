# StudyFlow Setup Guide

## Prerequisites

- Python 3.11+
- [notebooklm CLI](https://github.com/example/notebooklm-cli) — authenticated
- Claude Code with Notion MCP configured
- A Notion account with API access
- (Optional) yt-dlp and BeautifulSoup4 for source ingestion

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Set Up the Notion Workspace

Run the one-time setup command in Claude Code:

```
/studyflow setup
```

This creates:
- 📚 StudyFlow root page
- 📚 Knowledge Base database
- 🃏 Flashcard Vault database
- ❓ Quiz Bank database
- 📅 Study Sessions database
- 🗂️ Courses and Projects sections

After setup, copy the database IDs from the SKILL.md `Permanent Notion IDs` section
(printed by the setup command) to keep in your local SKILL.md.

## 3. Register the MCP Server (Claude Desktop)

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "studyflow": {
      "command": "python",
      "args": ["/path/to/studyflow_mcp_server.py"]
    }
  }
}
```

See `examples/claude_desktop_config.example.json` for a full example.

## 4. Install the Claude Code Skill

Copy `SKILL.md` to `~/.claude/skills/studyflow/SKILL.md`.

## 5. Start Studying

```
/studyflow notes "Your Notebook Name" --topic "Dynamic Programming"
```

## Dependencies

```
mcp>=1.0.0           # MCP SDK (required)
requests>=2.31.0     # HTTP client for web scraping
beautifulsoup4>=4.12.0  # HTML parsing
duckduckgo-search>=6.0.0  # Web search (no API key)
yt-dlp               # YouTube transcript extraction
```

Install all at once:
```bash
pip install -r requirements.txt
pip install yt-dlp  # yt-dlp is not on PyPI as a normal package
```

## Notion MCP

StudyFlow requires the Notion MCP server configured in Claude Code.
Add to your Claude Code MCP config and authenticate with your Notion account.

## notebooklm CLI

Install from: https://github.com/example/notebooklm-cli

Authenticate:
```bash
notebooklm login
```
