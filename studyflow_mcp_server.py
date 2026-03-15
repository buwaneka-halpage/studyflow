#!/usr/bin/env python3
"""
StudyFlow MCP Server
Exposes NotebookLM notebook management as MCP tools for Claude Desktop.

Tools:
  - studyflow_list_notebooks  — list all notebooks
  - studyflow_ask             — query a notebook
  - studyflow_add_url         — add URL directly to NotebookLM
  - studyflow_add_research    — NotebookLM web research → import all sources
  - studyflow_source_list     — list sources in a notebook
"""

import asyncio
import json
import os
import subprocess

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions

# ─── Helpers ────────────────────────────────────────────────────────────────

ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def run(cmd: list[str], check=True) -> str:
    """Run a shell command and return stdout as string."""
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return (result.stdout + result.stderr).strip()


def find_notebook_id(name: str) -> tuple[str, str]:
    """Fuzzy-match a notebook name to its ID. Returns (id, title)."""
    raw = run(["notebooklm", "list", "--json"])
    data = json.loads(raw)
    notebooks = data.get("notebooks", [])
    name_lower = name.lower()

    for nb in notebooks:
        if nb["title"].lower() == name_lower:
            return nb["id"], nb["title"]

    matches = [nb for nb in notebooks if name_lower in nb["title"].lower()]
    if len(matches) == 1:
        return matches[0]["id"], matches[0]["title"]
    if len(matches) > 1:
        titles = [nb["title"] for nb in matches]
        raise ValueError(f"Multiple notebooks match '{name}': {titles}. Be more specific.")

    titles = [nb["title"] for nb in notebooks]
    raise ValueError(f"No notebook found for '{name}'. Available: {titles}")


def set_notebook(notebook_id: str) -> None:
    run(["notebooklm", "use", notebook_id])


# ─── MCP Server ──────────────────────────────────────────────────────────────

server = Server("studyflow")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="studyflow_list_notebooks",
            description="List all NotebookLM notebooks with their IDs and titles.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="studyflow_add_url",
            description=(
                "Add a URL directly to a NotebookLM notebook without scraping. "
                "NotebookLM natively supports: web pages, YouTube URLs, PDFs, Google Docs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "notebook": {"type": "string", "description": "Notebook name"},
                    "url": {"type": "string", "description": "URL to add"},
                },
                "required": ["notebook", "url"],
            },
        ),
        types.Tool(
            name="studyflow_add_research",
            description=(
                "Use NotebookLM's web research feature to find and add sources on a topic. "
                "Modes: 'fast' (5-10 sources, seconds) or 'deep' (20+ sources, 2-5 minutes)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "notebook": {"type": "string", "description": "Notebook name"},
                    "query": {"type": "string", "description": "Topic or search query"},
                    "mode": {
                        "type": "string",
                        "enum": ["fast", "deep"],
                        "description": "Research depth (default: fast)",
                        "default": "fast",
                    },
                },
                "required": ["notebook", "query"],
            },
        ),
        types.Tool(
            name="studyflow_source_list",
            description="List all sources in a NotebookLM notebook with their status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "notebook": {"type": "string", "description": "Notebook name"},
                },
                "required": ["notebook"],
            },
        ),
        types.Tool(
            name="studyflow_ask",
            description="Ask a question to a NotebookLM notebook and get a grounded answer.",
            inputSchema={
                "type": "object",
                "properties": {
                    "notebook": {"type": "string", "description": "Notebook name"},
                    "question": {"type": "string", "description": "Question to ask"},
                },
                "required": ["notebook", "question"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        result = await _dispatch(name, arguments)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ Error: {e}")]


async def _dispatch(name: str, args: dict) -> str:
    if name == "studyflow_list_notebooks":
        raw = run(["notebooklm", "list", "--json"])
        data = json.loads(raw)
        notebooks = data.get("notebooks", [])
        lines = [f"Found {len(notebooks)} notebooks:\n"]
        for nb in notebooks:
            lines.append(f"  • {nb['title']} (id: {nb['id'][:8]}...)")
        return "\n".join(lines)

    elif name == "studyflow_add_url":
        nb_id, nb_title = find_notebook_id(args["notebook"])
        set_notebook(nb_id)
        out = run(["notebooklm", "source", "add", args["url"]])
        return f"✅ Added to '{nb_title}':\n{out[:400]}"

    elif name == "studyflow_add_research":
        nb_id, nb_title = find_notebook_id(args["notebook"])
        set_notebook(nb_id)
        mode = args.get("mode", "fast")
        query = args["query"]
        cmd = ["notebooklm", "source", "add-research", query, "--mode", mode, "--import-all"]
        out = run(cmd)
        return f"✅ Research completed for '{nb_title}':\n{out[:500]}"

    elif name == "studyflow_source_list":
        nb_id, nb_title = find_notebook_id(args["notebook"])
        set_notebook(nb_id)
        raw = run(["notebooklm", "source", "list", "--json"])
        data = json.loads(raw)
        sources = data.get("sources", [])
        lines = [f"Sources in '{nb_title}' ({len(sources)} total):\n"]
        for s in sources:
            status_icon = "✅" if s.get("status") == "ready" else "⏳"
            lines.append(f"  {status_icon} [{s['index']}] {s['title'][:70]}")
        return "\n".join(lines)

    elif name == "studyflow_ask":
        nb_id, nb_title = find_notebook_id(args["notebook"])
        set_notebook(nb_id)
        out = run(["notebooklm", "ask", args["question"]])
        return f"📚 Answer from '{nb_title}':\n\n{out}"

    else:
        return f"Unknown tool: {name}"


# ─── Entry point ─────────────────────────────────────────────────────────────

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="studyflow",
                server_version="0.2.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
