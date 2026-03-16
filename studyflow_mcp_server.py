#!/usr/bin/env python3
"""
StudyFlow MCP Server
Exposes NotebookLM source management as MCP tools for Claude Desktop.

Tools:
  - studyflow_list_notebooks       — list all notebooks
  - studyflow_find_sources         — multi-source search: YouTube + Web + arXiv in parallel
  - studyflow_search_youtube       — search YouTube and return ranked results
  - studyflow_add_youtube          — yt-dlp transcript → NotebookLM
  - studyflow_add_web              — scrape web page → NotebookLM
  - studyflow_add_url              — add URL directly to NotebookLM
  - studyflow_add_research         — NotebookLM web research → import all sources
  - studyflow_ask                  — query a notebook
  - studyflow_source_list          — list sources in a notebook
"""

import asyncio
import json
import os
import re
import subprocess
import sys
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

    # Exact match first
    for nb in notebooks:
        if nb["title"].lower() == name_lower:
            return nb["id"], nb["title"]

    # Partial match
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
    # Get video title for filename
    title_result = subprocess.run(
        ["yt-dlp", "--print", "%(title)s", "--no-playlist", url],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    title = re.sub(r'[^\w\s-]', '', title_result.stdout.strip())[:60] or "transcript"
    out_base = os.path.join(out_dir, title)

    # Try to get auto-generated or manual subtitles
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

    # Find the downloaded .vtt file
    vtt_files = list(Path(out_dir).glob("*.vtt"))
    if not vtt_files:
        # Fallback: use video description
        info_result = subprocess.run(
            ["yt-dlp", "--print", "%(title)s\n%(description)s", "--no-playlist", url],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        txt_path = out_base + "_description.txt"
        Path(txt_path).write_text(info_result.stdout, encoding="utf-8")
        return txt_path

    vtt_path = str(vtt_files[0])

    # Convert VTT → clean text (remove timestamps and formatting)
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
        if re.match(r'^\d{2}:\d{2}', line):  # timestamp
            continue
        if re.match(r'^\d+$', line):  # sequence number
            continue
        # Strip HTML-like tags
        line = re.sub(r'<[^>]+>', '', line)
        if line and line not in seen:
            seen.add(line)
            text_lines.append(line)

    clean_text = "\n".join(text_lines)
    txt_path = out_base + "_transcript.txt"
    Path(txt_path).write_text(clean_text, encoding="utf-8")

    # Clean up vtt
    Path(vtt_path).unlink(missing_ok=True)
    return txt_path


# ─── Web scraping ─────────────────────────────────────────────────────────────

def scrape_web_page(url: str) -> str:
    """
    Scrape a web page and return clean article text.
    Handles GeeksForGeeks, MDN, Wikipedia, generic sites.
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

    # Remove noise elements
    for tag in soup(["script", "style", "nav", "footer", "header",
                      "aside", "advertisement", "iframe", "noscript",
                      ".advertisement", "#advertisement"]):
        tag.decompose()

    # Site-specific content selectors
    domain = url.lower()
    content = None

    if "geeksforgeeks.org" in domain:
        content = soup.find("article") or soup.find("div", class_=re.compile(r"content|article|post"))
    elif "wikipedia.org" in domain:
        content = soup.find("div", id="mw-content-text")
    elif "developer.mozilla.org" in domain or "mdn" in domain:
        content = soup.find("article") or soup.find("main")
    elif "stackoverflow.com" in domain:
        # Get question + accepted answer
        question = soup.find("div", class_=re.compile(r"question"))
        answer = soup.find("div", class_=re.compile(r"answer.*accepted|accepted.*answer"))
        content_parts = []
        if question:
            content_parts.append(question.get_text(separator="\n"))
        if answer:
            content_parts.append("--- ACCEPTED ANSWER ---\n" + answer.get_text(separator="\n"))
        if content_parts:
            return "\n\n".join(content_parts)
    elif "medium.com" in domain or "towardsdatascience.com" in domain:
        content = soup.find("article")
    else:
        # Generic: try article > main > body with largest text block
        content = (
            soup.find("article") or
            soup.find("main") or
            soup.find("div", id=re.compile(r"content|main|article", re.I)) or
            soup.find("div", class_=re.compile(r"content|main|article|post", re.I))
        )

    if content:
        text = content.get_text(separator="\n")
    else:
        text = soup.get_text(separator="\n")

    # Clean up whitespace
    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line and len(line) > 2]
    # Remove duplicate lines
    seen = set()
    unique_lines = []
    for line in lines:
        if line not in seen:
            seen.add(line)
            unique_lines.append(line)

    return "\n".join(unique_lines)


# ─── Multi-source search helpers ─────────────────────────────────────────────

# Trusted high-quality domains for CSE learning
TRUSTED_DOMAINS = {
    # Documentation / reference
    "developer.mozilla.org": ("MDN Docs", 10),
    "docs.python.org": ("Python Docs", 10),
    "cppreference.com": ("CppReference", 10),
    "docs.oracle.com": ("Oracle Docs", 9),
    # Academic / textbook
    "geeksforgeeks.org": ("GeeksForGeeks", 8),
    "cp-algorithms.com": ("CP Algorithms", 9),
    "programiz.com": ("Programiz", 7),
    "tutorialspoint.com": ("TutorialsPoint", 6),
    # University resources
    "ocw.mit.edu": ("MIT OCW", 10),
    "cs.stanford.edu": ("Stanford CS", 10),
    "web.cs.ucla.edu": ("UCLA CS", 9),
    # Stack Overflow + forums
    "stackoverflow.com": ("Stack Overflow", 8),
    "cs.stackexchange.com": ("CS StackExchange", 9),
    # General tech
    "medium.com": ("Medium", 5),
    "towardsdatascience.com": ("Towards Data Science", 7),
    "freecodecamp.org": ("freeCodeCamp", 7),
    "baeldung.com": ("Baeldung", 7),
    "realpython.com": ("Real Python", 8),
    # Research
    "arxiv.org": ("arXiv", 10),
    "paperswithcode.com": ("Papers With Code", 9),
}


def domain_score(url: str) -> tuple[str, int]:
    """Return (label, quality_score) for a URL's domain."""
    for domain, (label, score) in TRUSTED_DOMAINS.items():
        if domain in url:
            return label, score
    return "Web", 3


def search_web(query: str, count: int = 8) -> list[dict]:
    """Search DuckDuckGo and return structured results."""
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=count):
                label, score = domain_score(r.get("href", ""))
                results.append({
                    "type": "web",
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")[:200],
                    "source_label": label,
                    "quality_score": score,
                })
        return results
    except Exception as e:
        return [{"type": "error", "title": f"Web search failed: {e}", "url": "", "snippet": "", "source_label": "Error", "quality_score": 0}]


def search_arxiv(query: str, count: int = 5) -> list[dict]:
    """Search arXiv for academic papers (free API, no key needed)."""
    try:
        import urllib.request
        import xml.etree.ElementTree as ET

        encoded = urllib.parse.quote(query)
        url = f"https://export.arxiv.org/api/query?search_query=all:{encoded}&max_results={count}&sortBy=relevance"
        with urllib.request.urlopen(url, timeout=10) as resp:
            xml_data = resp.read().decode("utf-8")

        root = ET.fromstring(xml_data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        results = []
        for entry in root.findall("atom:entry", ns):
            title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
            link_el = entry.find("atom:link[@rel='alternate']", ns)
            paper_url = link_el.get("href", "") if link_el is not None else ""
            if not paper_url:
                id_el = entry.findtext("atom:id", "", ns)
                paper_url = id_el
            summary = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")[:200]
            published = entry.findtext("atom:published", "", ns)[:10]
            results.append({
                "type": "arxiv",
                "title": title,
                "url": paper_url,
                "snippet": summary,
                "source_label": f"arXiv ({published})",
                "quality_score": 10,
            })
        return results
    except Exception as e:
        return [{"type": "error", "title": f"arXiv search failed: {e}", "url": "", "snippet": "", "source_label": "Error", "quality_score": 0}]


def search_youtube_raw(query: str, count: int = 5) -> list[dict]:
    """yt-dlp YouTube search, returns structured dicts."""
    result = subprocess.run(
        [
            "yt-dlp", f"ytsearch{count}:{query}",
            "--print", "%(title)s\t%(webpage_url)s\t%(duration_string)s\t%(channel)s\t%(view_count)s",
            "--no-playlist", "--skip-download", "--no-warnings",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    videos = []
    for line in result.stdout.strip().split("\n"):
        if "\t" not in line:
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        title, url, duration, channel = parts[0], parts[1], parts[2], parts[3]
        views_raw = parts[4] if len(parts) > 4 else "0"
        try:
            views = int(views_raw)
        except ValueError:
            views = 0

        # Parse duration to seconds
        dur_secs = 0
        try:
            p = duration.split(":")
            if len(p) == 3:
                dur_secs = int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])
            elif len(p) == 2:
                dur_secs = int(p[0]) * 60 + int(p[1])
        except Exception:
            pass

        # Score: longer educational videos + views boost ranking
        view_score = min(views / 500_000, 3)   # cap at 3 bonus points
        duration_score = min(dur_secs / 600, 4)  # cap at 4 for ~10 min+
        quality_score = 5 + view_score + duration_score

        videos.append({
            "type": "youtube",
            "title": title,
            "url": url,
            "snippet": f"{channel} · {duration} · {views:,} views" if views else f"{channel} · {duration}",
            "source_label": f"YouTube ({channel})",
            "quality_score": quality_score,
            "dur_secs": dur_secs,
            "views": views,
        })
    return videos


import urllib.parse  # needed by search_arxiv


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
            name="studyflow_find_sources",
            description=(
                "Multi-source search for learning material on any topic. "
                "Searches YouTube (via yt-dlp), the web (DuckDuckGo), and academic papers (arXiv) "
                "in parallel and returns unified ranked results grouped by source type. "
                "Results include quality scores — trusted domains (MIT OCW, MDN, GfG, arXiv) score higher. "
                "Use this as your first step when building a NotebookLM notebook on a new topic."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to search for (e.g. 'merge sort algorithm', 'React hooks', 'transformer architecture')",
                    },
                    "sources": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["youtube", "web", "arxiv"]},
                        "description": "Which source types to search (default: ['youtube', 'web']). Add 'arxiv' for research-heavy topics.",
                        "default": ["youtube", "web"],
                    },
                    "count_per_source": {
                        "type": "integer",
                        "description": "Results per source type (default: 5)",
                        "default": 5,
                    },
                    "cse_context": {
                        "type": "string",
                        "description": "Optional CSE context to refine results (e.g. 'undergraduate algorithms course', 'system design interview')",
                    },
                },
                "required": ["topic"],
            },
        ),
        types.Tool(
            name="studyflow_search_youtube",
            description=(
                "Search YouTube for videos matching a query and return ranked results "
                "with title, URL, duration, channel, and view count. "
                "Use this before studyflow_add_youtube to find the right video."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g. 'dynamic programming MIT lecture', 'React hooks tutorial')",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5, max: 20)",
                        "default": 5,
                    },
                    "filter": {
                        "type": "string",
                        "enum": ["any", "lecture", "tutorial", "short"],
                        "description": (
                            "Filter results: 'lecture' prefers university/conference talks (>30 min), "
                            "'tutorial' prefers step-by-step coding videos, "
                            "'short' prefers videos under 15 minutes. "
                            "Default: 'any'."
                        ),
                        "default": "any",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="studyflow_add_youtube",
            description=(
                "Add a YouTube video to a NotebookLM notebook. "
                "Extracts the transcript as a text file using yt-dlp and uploads it as a source. "
                "Use this for YouTube lecture videos, tutorials, talks, etc."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "notebook": {
                        "type": "string",
                        "description": "Notebook name (partial match OK, e.g. 'AI agent', 'DSA')",
                    },
                    "youtube_url": {
                        "type": "string",
                        "description": "Full YouTube video URL",
                    },
                    "as_url": {
                        "type": "boolean",
                        "description": "If true, add the YouTube URL directly instead of extracting transcript (faster, less text)",
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
                "Works best with: GeeksForGeeks, MDN, Wikipedia, Stack Overflow, Medium, "
                "documentation sites, and most article/blog pages."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "notebook": {
                        "type": "string",
                        "description": "Notebook name (partial match OK)",
                    },
                    "url": {
                        "type": "string",
                        "description": "Web page URL to scrape",
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional custom title for the source",
                    },
                },
                "required": ["notebook", "url"],
            },
        ),
        types.Tool(
            name="studyflow_add_url",
            description=(
                "Add a URL directly to a NotebookLM notebook without scraping. "
                "NotebookLM natively supports: web pages, YouTube URLs, PDFs, Google Docs. "
                "Use studyflow_add_web for sites that may have scraping issues."
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
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        result = await _dispatch(name, arguments)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        return [types.TextContent(type="text", text=f"❌ Error: {e}")]


async def _dispatch(name: str, args: dict) -> str:
    # ── List notebooks ───────────────────────────────────────────────────────
    if name == "studyflow_list_notebooks":
        raw = run(["notebooklm", "list", "--json"])
        data = json.loads(raw)
        notebooks = data.get("notebooks", [])
        lines = [f"Found {len(notebooks)} notebooks:\n"]
        for nb in notebooks:
            lines.append(f"  • {nb['title']} (id: {nb['id'][:8]}...)")
        return "\n".join(lines)

    # ── Find sources (multi-source) ──────────────────────────────────────────
    elif name == "studyflow_find_sources":
        topic = args["topic"]
        sources = args.get("sources", ["youtube", "web"])
        count = int(args.get("count_per_source", 5))
        cse_context = args.get("cse_context", "")

        base_query = f"{topic} {cse_context}".strip()
        yt_query = f"{topic} lecture tutorial explained {cse_context}".strip()

        # Run searches in parallel using threads
        import concurrent.futures
        all_results: dict[str, list[dict]] = {}

        def _yt():
            return search_youtube_raw(yt_query, count)

        def _web():
            return search_web(f"{base_query} tutorial explanation", count)

        def _arxiv():
            return search_arxiv(base_query, min(count, 5))

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = {}
            if "youtube" in sources:
                futures["youtube"] = pool.submit(_yt)
            if "web" in sources:
                futures["web"] = pool.submit(_web)
            if "arxiv" in sources:
                futures["arxiv"] = pool.submit(_arxiv)

            for key, fut in futures.items():
                try:
                    all_results[key] = fut.result(timeout=30)
                except Exception as e:
                    all_results[key] = [{"type": "error", "title": f"{key} search failed: {e}", "url": "", "snippet": "", "source_label": "Error", "quality_score": 0}]

        icon = {"youtube": "📹 YouTube", "web": "🌐 Web Articles", "arxiv": "📄 Academic Papers"}

        item_num = 1
        lines = [f"🔍 Source search: '{topic}'\n"]
        if cse_context:
            lines.append(f"   Context: {cse_context}\n")

        for src_type in ["youtube", "web", "arxiv"]:
            if src_type not in all_results:
                continue
            results = all_results[src_type]
            valid = [r for r in results if r.get("url")]
            errors = [r for r in results if not r.get("url")]

            lines.append(f"\n{'─'*60}")
            lines.append(f"{icon.get(src_type, src_type)} ({len(valid)} results)")
            lines.append(f"{'─'*60}")

            for r in valid:
                score_bar = "★" * min(int(r["quality_score"]), 10)
                lines.append(
                    f"\n[{item_num}] {r['title']}\n"
                    f"    {r['source_label']}  {score_bar}\n"
                    f"    {r['snippet'][:150]}\n"
                    f"    🔗 {r['url']}"
                )
                item_num += 1

            for e in errors:
                lines.append(f"    ⚠️ {e['title']}")

        lines.append(f"\n{'─'*60}")
        lines.append(f"Total: {item_num - 1} sources found")
        lines.append("\nTo add sources to a notebook:")
        lines.append("  • YouTube: studyflow_add_youtube(notebook='...', youtube_url='<url>')")
        lines.append("  • Web/arXiv: studyflow_add_web(notebook='...', url='<url>')")

        return "\n".join(lines)

    # ── Search YouTube ───────────────────────────────────────────────────────
    elif name == "studyflow_search_youtube":
        query = args["query"]
        count = min(int(args.get("count", 5)), 20)
        filter_type = args.get("filter", "any")

        result = subprocess.run(
            [
                "yt-dlp",
                f"ytsearch{count}:{query}",
                "--print", "%(title)s\t%(webpage_url)s\t%(duration_string)s\t%(channel)s\t%(view_count)s",
                "--no-playlist",
                "--skip-download",
                "--no-warnings",
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )

        raw_lines = [l for l in result.stdout.strip().split("\n") if "\t" in l]

        if not raw_lines:
            return (
                f"No results found for '{query}'.\n"
                f"yt-dlp output: {result.stderr[:300] or '(empty)'}"
            )

        videos = []
        for line in raw_lines:
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            title, url, duration, channel = parts[0], parts[1], parts[2], parts[3]
            views_raw = parts[4] if len(parts) > 4 else "0"
            try:
                views = int(views_raw)
            except ValueError:
                views = 0

            dur_secs = 0
            try:
                dur_parts = duration.split(":")
                if len(dur_parts) == 3:
                    dur_secs = int(dur_parts[0]) * 3600 + int(dur_parts[1]) * 60 + int(dur_parts[2])
                elif len(dur_parts) == 2:
                    dur_secs = int(dur_parts[0]) * 60 + int(dur_parts[1])
            except Exception:
                pass

            videos.append({
                "title": title,
                "url": url,
                "duration": duration or "?",
                "channel": channel or "?",
                "views": views,
                "dur_secs": dur_secs,
            })

        # Apply filter re-ranking (not filtering — avoids zero results)
        if filter_type == "lecture":
            lectures = [v for v in videos if v["dur_secs"] > 1800]
            if lectures:
                videos = sorted(lectures, key=lambda v: v["dur_secs"], reverse=True) + \
                         [v for v in videos if v["dur_secs"] <= 1800]
        elif filter_type == "tutorial":
            tutorials = [v for v in videos if 300 <= v["dur_secs"] <= 3600]
            if tutorials:
                videos = sorted(tutorials, key=lambda v: v["views"], reverse=True) + \
                         [v for v in videos if not (300 <= v["dur_secs"] <= 3600)]
        elif filter_type == "short":
            shorts = [v for v in videos if v["dur_secs"] < 900]
            if shorts:
                videos = shorts + [v for v in videos if v["dur_secs"] >= 900]

        lines = [f"🔍 YouTube search: '{query}' — {len(videos)} results\n"]
        for i, v in enumerate(videos, 1):
            views_str = f"{v['views']:,}" if v["views"] else "?"
            lines.append(
                f"{i}. {v['title']}\n"
                f"   📺 {v['channel']}  ⏱ {v['duration']}  👁 {views_str} views\n"
                f"   🔗 {v['url']}\n"
            )

        lines.append("─" * 60)
        lines.append("To add a video: studyflow_add_youtube(notebook='...', youtube_url='<URL from above>')")

        return "\n".join(lines)

    # ── Add YouTube ──────────────────────────────────────────────────────────
    elif name == "studyflow_add_youtube":
        notebook, url = args["notebook"], args["youtube_url"]
        as_url = args.get("as_url", False)

        nb_id, nb_title = find_notebook_id(notebook)
        set_notebook(nb_id)

        if as_url:
            out = run(["notebooklm", "source", "add", url])
            return f"✅ Added YouTube URL to '{nb_title}':\n{out}"

        # Extract transcript via yt-dlp
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = extract_youtube_transcript(url, tmpdir)
            fname = Path(txt_path).name
            out = run(["notebooklm", "source", "add", txt_path])
            return (
                f"✅ Transcript extracted and added to '{nb_title}'.\n"
                f"File: {fname}\n"
                f"NotebookLM response: {out[:300]}"
            )

    # ── Add web page ─────────────────────────────────────────────────────────
    elif name == "studyflow_add_web":
        notebook, url = args["notebook"], args["url"]
        custom_title = args.get("title", "")

        nb_id, nb_title = find_notebook_id(notebook)
        set_notebook(nb_id)

        # Scrape the page
        content = scrape_web_page(url)
        char_count = len(content)

        if char_count < 200:
            return (
                f"⚠️ Only {char_count} chars extracted from {url}. "
                "The site may require JavaScript. "
                "Try studyflow_add_url to add it directly, or use Playwright."
            )

        # Build title from URL if not provided
        if not custom_title:
            slug = re.sub(r'[^\w-]', '-', url.split("/")[-1] or url.split("/")[-2])[:50]
            custom_title = slug or "scraped-page"

        # Save to temp file and upload
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", prefix=f"{custom_title}_",
            delete=False, encoding="utf-8"
        ) as f:
            header = f"Source URL: {url}\nTitle: {custom_title}\n{'='*60}\n\n"
            f.write(header + content)
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

    # ── Add URL directly ─────────────────────────────────────────────────────
    elif name == "studyflow_add_url":
        nb_id, nb_title = find_notebook_id(args["notebook"])
        set_notebook(nb_id)
        out = run(["notebooklm", "source", "add", args["url"]])
        return f"✅ Added to '{nb_title}':\n{out[:400]}"

    # ── Add research ─────────────────────────────────────────────────────────
    elif name == "studyflow_add_research":
        nb_id, nb_title = find_notebook_id(args["notebook"])
        set_notebook(nb_id)
        mode = args.get("mode", "fast")
        query = args["query"]
        cmd = ["notebooklm", "source", "add-research", query, "--mode", mode, "--import-all"]
        out = run(cmd)
        return f"✅ Research completed for '{nb_title}':\n{out[:500]}"

    # ── Ask notebook ─────────────────────────────────────────────────────────
    elif name == "studyflow_ask":
        nb_id, nb_title = find_notebook_id(args["notebook"])
        set_notebook(nb_id)
        out = run(["notebooklm", "ask", args["question"]])
        return f"📚 Answer from '{nb_title}':\n\n{out}"

    # ── Source list ──────────────────────────────────────────────────────────
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
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
