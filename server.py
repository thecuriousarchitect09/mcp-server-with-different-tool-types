"""
Simple local MCP (Model Context Protocol) server.

Exposes 5 general-purpose utility tools:
  1. read_file     - read a text file from disk
  2. write_file     - write/overwrite a text file on disk
  3. fetch_url      - fetch a URL and return readable text content
  4. calculate      - safely evaluate a math expression
  5. run_command    - run a shell command (restricted, with timeout)

Built with the official Python MCP SDK (FastMCP), using the Streamable
HTTP transport. This is "self-running": just execute this file and it
starts an HTTP server that listens on its own (no external `mcp dev` /
client process needs to spawn it, unlike stdio servers).

Run it:
    python server.py
    # -> Uvicorn running on http://127.0.0.1:8000/mcp

Override host/port with env vars:
    MCP_HOST=0.0.0.0 MCP_PORT=9000 python server.py

See README.md for how to point a client at it.
"""

import ast
import operator
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from mcp.server.mcpserver import MCPServer  # mcp>=2.0; FastMCP was renamed to this

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

HOST = os.environ.get("MCP_HOST", "127.0.0.1")
PORT = int(os.environ.get("MCP_PORT", "8000"))

mcp = MCPServer("utility-server")

# Restrict file tools to a sandbox directory by default so the server can't
# read/write arbitrary paths on your machine unless you widen this.
# Change to Path("/") to allow the whole filesystem (not recommended).
BASE_DIR = Path.home() / "mcp-sandbox"
BASE_DIR.mkdir(parents=True, exist_ok=True)

# Commands allowed for run_command. Keep this short and boring on purpose;
# expand it deliberately, don't remove the allowlist entirely.
ALLOWED_COMMANDS = {"ls", "pwd", "whoami", "date", "echo", "cat", "df", "uname"}


def _resolve_in_sandbox(path_str: str) -> Path:
    """Resolve a user-supplied path safely inside BASE_DIR."""
    candidate = (BASE_DIR / path_str).resolve()
    if not str(candidate).startswith(str(BASE_DIR.resolve())):
        raise ValueError(
            f"Path '{path_str}' resolves outside the sandbox directory "
            f"({BASE_DIR}). Refusing to access it."
        )
    return candidate


# ---------------------------------------------------------------------------
# Tool 1: read_file
# ---------------------------------------------------------------------------

@mcp.tool()
def read_file(path: str) -> str:
    """Read the contents of a text file.

    Args:
        path: Path relative to the sandbox directory (~/mcp-sandbox).
              e.g. "notes.txt" or "subdir/data.json".
    """
    target = _resolve_in_sandbox(path)
    if not target.exists():
        return f"Error: file not found: {target}"
    if not target.is_file():
        return f"Error: not a file: {target}"
    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: '{path}' is not a UTF-8 text file (binary?)."


# ---------------------------------------------------------------------------
# Tool 2: write_file
# ---------------------------------------------------------------------------

@mcp.tool()
def write_file(path: str, content: str, overwrite: bool = True) -> str:
    """Write text content to a file, creating parent directories as needed.

    Args:
        path: Path relative to the sandbox directory (~/mcp-sandbox).
        content: Text content to write.
        overwrite: If False and the file already exists, the write is
                   refused instead of overwriting it.
    """
    target = _resolve_in_sandbox(path)
    if target.exists() and not overwrite:
        return f"Error: '{path}' already exists and overwrite=False."
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} chars to {target}"


# ---------------------------------------------------------------------------
# Tool 3: fetch_url
# ---------------------------------------------------------------------------

@mcp.tool()
def fetch_url(url: str, max_chars: int = 5000) -> str:
    """Fetch a URL over HTTP(S) and return its text content (HTML stripped).

    Args:
        url: The http:// or https:// URL to fetch.
        max_chars: Truncate returned text to this many characters (default 5000).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "Error: only http:// and https:// URLs are allowed."

    try:
        resp = requests.get(
            url,
            timeout=10,
            headers={"User-Agent": "local-mcp-utility-server/1.0"},
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return f"Error fetching URL: {exc}"

    content_type = resp.headers.get("content-type", "")
    text = resp.text

    if "html" in content_type:
        # Minimal, dependency-free tag stripping. Good enough for quick
        # reads; swap in BeautifulSoup if you need robust extraction.
        import re

        text = re.sub(r"<script.*?</script>", "", text, flags=re.S | re.I)
        text = re.sub(r"<style.*?</style>", "", text, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

    return text[:max_chars]


# ---------------------------------------------------------------------------
# Tool 4: calculate
# ---------------------------------------------------------------------------

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


@mcp.tool()
def calculate(expression: str) -> str:
    """Safely evaluate a numeric math expression (+, -, *, /, //, %, **).

    Does not use eval(); only arithmetic on numbers is permitted, so
    this is safe to expose even to untrusted input.

    Args:
        expression: e.g. "2 + 2 * (3 - 1) ** 2"
    """
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)
    except Exception as exc:
        return f"Error: could not evaluate '{expression}': {exc}"
    return str(result)


# ---------------------------------------------------------------------------
# Tool 5: run_command
# ---------------------------------------------------------------------------

@mcp.tool()
def run_command(command: str, timeout_seconds: int = 10) -> str:
    """Run a whitelisted, read-only shell command and return its output.

    Only the following commands are permitted: ls, pwd, whoami, date,
    echo, cat, df, uname. This is intentionally restrictive since this
    tool executes on your real machine — expand ALLOWED_COMMANDS in
    server.py deliberately, and never allow arbitrary shell input.

    Args:
        command: The full command line, e.g. "ls -la" or "date +%Y".
        timeout_seconds: Kill the command if it runs longer than this.
    """
    parts = command.strip().split()
    if not parts:
        return "Error: empty command."
    program = parts[0]
    if program not in ALLOWED_COMMANDS:
        return (
            f"Error: '{program}' is not in the allowlist "
            f"({sorted(ALLOWED_COMMANDS)}). Edit ALLOWED_COMMANDS in "
            f"server.py to permit it."
        )
    try:
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=BASE_DIR,
        )
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout_seconds}s."
    except FileNotFoundError:
        return f"Error: command not found: {program}"

    output = result.stdout
    if result.returncode != 0:
        output += f"\n[exit code {result.returncode}]\n{result.stderr}"
    return output or "(no output)"



# ============================================================
# 1. TOOL
# ============================================================

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


# ============================================================
# 2. RESOURCE
# ============================================================

@mcp.resource("demo://greeting")
def greeting() -> str:
    """A simple greeting resource."""
    return "Hello from my MCP server!"


# ============================================================
# 3. RESOURCE WITH A PARAMETER
# ============================================================

@mcp.resource("demo://user/{name}")
def user_info(name: str) -> str:
    """Return information about a user."""
    return f"User name: {name}\nStatus: Active"


# ============================================================
# 4. PROMPT
# ============================================================

@mcp.prompt()
def explain_topic(topic: str) -> str:
    """Create a prompt for explaining a topic."""
    return f"""
        Explain {topic} in simple terms.

        Include:
        1. What it is
        2. Why it is useful
        3. A simple example
        """

if __name__ == "__main__":
    print(f"Starting MCP HTTP server on http://{HOST}:{PORT}/mcp")
    mcp.run(transport="streamable-http", host=HOST, port=PORT)