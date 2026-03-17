# Claude Desktop MCP Server Setup

## What This Enables

Installing `studyflow_mcp_server.py` as a Claude Desktop MCP server gives you
**9 tools** directly in Claude Desktop conversations:

| Tool | Description |
|------|-------------|
| `studyflow_list_notebooks` | List all NotebookLM notebooks |
| `studyflow_find_sources` | Search YouTube + Web + arXiv in parallel |
| `studyflow_search_youtube` | YouTube search with filter modes |
| `studyflow_add_youtube` | Extract transcript → NotebookLM |
| `studyflow_add_web` | Scrape web page → NotebookLM |
| `studyflow_add_url` | Add URL directly to NotebookLM |
| `studyflow_add_research` | NotebookLM web research import |
| `studyflow_ask` | Query a notebook |
| `studyflow_source_list` | List sources in a notebook |

## Installation

1. Find your Claude Desktop config:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`

2. Add the `studyflow` server:
   ```json
   {
     "mcpServers": {
       "studyflow": {
         "command": "python",
         "args": ["/absolute/path/to/studyflow_mcp_server.py"]
       }
     }
   }
   ```

3. Restart Claude Desktop completely.

4. Verify: In a new conversation, ask Claude to list your notebooks.
   The `studyflow_list_notebooks` tool should appear in the tool list.

## Troubleshooting

**Server appears to crash when run manually in terminal**
This is expected — the MCP server communicates via stdio pipes. It only works
when launched by Claude Desktop (or another MCP client). Running it directly
in a terminal will show no output and appear to hang.

**"No notebook found" errors**
Make sure `notebooklm login` has been run and you have notebooks created at
notebooklm.google.com.

**Unicode errors on Windows**
The server sets `PYTHONIOENCODING=utf-8` automatically. If you see encoding
errors in Claude Desktop logs, ensure Python 3.11+ is being used.
