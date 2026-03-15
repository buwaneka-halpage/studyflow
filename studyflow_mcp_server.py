#!/usr/bin/env python3
"""
StudyFlow MCP Server
Exposes NotebookLM source management as MCP tools for Claude Desktop.

Tools:
  - studyflow_list_notebooks  — list all notebooks
  - studyflow_ask             — query a notebook
  - studyflow_add_url         — add URL directly to NotebookLM
  - studyflow_add_research    — NotebookLM web research → import all sources
  - studyflow_add_youtube     — yt-dlp transcript → NotebookLM
  - studyflow_add_web         — scrape web page → NotebookLM
  - studyflow_source_list     — list sources in a notebook
"""

import asyncio
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

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


# ─── yt-dlp transcript extraction ────────────────────────────────────────────

def extract_youtube_transcript(url: str, out_dir: str) -> str:
    """
    Use yt-dlp to extract a YouTube transcript/subtitles as clean text.
    Returns path to the saved .txt file.
    """
    title_result = subprocess.run(
        ["yt-dlp", "--print", "%(title)s", "--no-playlist", url],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    title = re.sub(r'[^\w\s-]', '', title_result.stdout.strip())[:60] or "transcript"
    out_base = os.path.join(out_dir, title)

    subprocess.run(
        [
            "yt-dlp",
            "--write-subs", "--write-auto-subs",
            "--sub-lang", "en",
            "--sub-format", "vtt",
            "--skip-download",
            "--no-playlist",
            "-o", out_base,
            url,
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )

    vtt_files = list(Path(out_dir).glob("*.vtt"))
    if not vtt_files:
        info_result = subprocess.run(
            ["yt-dlp", "--print", "%(title)s\n%(description)s", "--no-playlist", url],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        txt_path = out_base + "_description.txt"
        Path(txt_path).write_text(info_result.stdout, encoding="utf-8")
        return txt_path

    vtt_path = str(vtt_files[0])
    vtt_content = Path(vtt_path).read_text(encoding="utf-8", errors="replace")
    lines = vtt_content.split("\n")
    text_lines = []
    seen = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if re.match(r'^\d{2}:\d{2}', line):
            continue
        if re.match(r'^\d+$', line):
            continue
        line = re.sub(r'<[^>]+>', '', line)
        if line and line not in seen:
            seen.add(line)
            text_lines.append(line)

    clean_text = "\n".join(text_lines)
    txt_path = out_base + "_transcript.txt"
    Path(txt_path).write_text(clean_text, encoding="utf-8")
    Path(vtt_path).unlink(missing_ok=True)
    return txt_path


# ─── Web scraping ─────────────────────────────────────────────────────────────

def scrape_web_page(url: str) -> str:
    """
    Scrape a web page and return clean article text.
    Uses site-specific selectors for best results on common CSE learning sites.
    """
    import requests
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove noise
    for tag in soup(["script", "style", "nav", "footer", "header",
                      "aside", "advertisement", "iframe", "noscript"]):
        tag.decompose()

    # Site-specific content selectors
    domain = url.lower()
    content = None

    if "geeksforgeeks.org" in domain:
        content = soup.find("article") or soup.find("div", class_=re.compile(r"content|article|post"))
    elif "wikipedia.org" in domain:
        content = soup.find("div", id="mw-content-text")
    elif "developer.mozilla.org" in domain:
        content = soup.find("article") or soup.find("main")
    elif "stackoverflow.com" in domain:
        question = soup.find("div", class_=re.compile(r"question"))
        answer = soup.find("div", class_=re.compile(r"answer.*accepted|accepted.*answer"))
        parts = []
        if question:
            parts.append(question.get_text(separator="\n"))
        if answer:
            parts.append("--- ACCEPTED ANSWER ---\n" + answer.get_text(separator="\n"))
        if parts:
            return "\n\n".join(parts)
    elif "medium.com" in domain or "towardsdatascience.com" in domain:
        content = soup.find("article")
    else:
        content = (
            soup.find("article") or
            soup.find("main") or
            soup.find("div", id=re.compile(r"content|main|article", re.I)) or
            soup.find("div", class_=re.compile(r"content|main|article|post", re.I))
        )

    text = content.get_text(separator="\n") if content else soup.get_text(separator="\n")

    # Clean up whitespace and deduplicate
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line and len(line) > 2]
    seen: set[str] = set()
    unique_lines = []
    for line in lines:
        if line not in seen:
            seen.add(line)
            unique_lines.append(line)

    return "\n".join(unique_lines)


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
            name="studyflow_add_youtube",
            description=(
                "Add a YouTube video to a NotebookLM notebook. "
                "Extracts the transcript as a text file using yt-dlp and uploads it as a source."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "notebook": {"type": "string", "description": "Notebook name (partial match OK)"},
                    "youtube_url": {"type": "string", "description": "Full YouTube video URL"},
                    "as_url": {
                        "type": "boolean",
                        "description": "If true, add the YouTube URL directly instead of extracting transcript",
                        "default": False,
                    },
                },
                "required": ["notebook", "youtube_url"],
            },
        ),
        types.Tool(
            name="studyflow_add_web",
            description=(
                "Scrape a web page and add its content as a source in a NotebookLM notebook. "
                "Works best with: GeeksForGeeks, MDN, Wikipedia, Stack Overflow, Medium."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "notebook": {"type": "string", "description": "Notebook name (partial match OK)"},
                    "url": {"type": "string", "description": "Web page URL to scrape"},
                    "title": {"type": "string", "description": "Optional custom title for the source"},
                },
                "required": ["notebook", "url"],
            },
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

    elif name == "studyflow_add_youtube":
        notebook, url = args["notebook"], args["youtube_url"]
        as_url = args.get("as_url", False)
        nb_id, nb_title = find_notebook_id(notebook)
        set_notebook(nb_id)

        if as_url:
            out = run(["notebooklm", "source", "add", url])
            return f"✅ Added YouTube URL to '{nb_title}':\n{out}"

        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = extract_youtube_transcript(url, tmpdir)
            fname = Path(txt_path).name
            out = run(["notebooklm", "source", "add", txt_path])
            return (
                f"✅ Transcript extracted and added to '{nb_title}'.\n"
                f"File: {fname}\n"
                f"NotebookLM response: {out[:300]}"
            )

    elif name == "studyflow_add_web":
        notebook, url = args["notebook"], args["url"]
        custom_title = args.get("title", "")
        nb_id, nb_title = find_notebook_id(notebook)
        set_notebook(nb_id)

        content = scrape_web_page(url)
        char_count = len(content)

        if char_count < 200:
            return (
                f"⚠️ Only {char_count} chars extracted from {url}. "
                "The site may require JavaScript. "
                "Try studyflow_add_url to add it directly."
            )

        if not custom_title:
            slug = re.sub(r'[^\w-]', '-', url.split("/")[-1] or url.split("/")[-2])[:50]
            custom_title = slug or "scraped-page"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", prefix=f"{custom_title}_",
            delete=False, encoding="utf-8"
        ) as f:
            f.write(f"Source URL: {url}\nTitle: {custom_title}\n{'='*60}\n\n" + content)
            tmp_path = f.name

        try:
            out = run(["notebooklm", "source", "add", tmp_path])
            return (
                f"✅ Scraped {char_count:,} chars from {url}\n"
                f"Added to '{nb_title}' as '{custom_title}'\n"
                f"NotebookLM: {out[:200]}"
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

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
        out = run(["notebooklm", "source", "add-research", query, "--mode", mode, "--import-all"])
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
                server_version="0.4.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
