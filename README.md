# Local Utility MCP Server

A minimal, local Python MCP server exposing 5 general-purpose tools, built
with the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
(`FastMCP`).

## Tools

| Tool | Description |
|---|---|
| `read_file(path)` | Read a text file from the sandbox dir (`~/mcp-sandbox`) |
| `write_file(path, content, overwrite=True)` | Write a text file into the sandbox dir |
| `fetch_url(url, max_chars=5000)` | HTTP GET a URL, strip HTML, return text |
| `calculate(expression)` | Safely evaluate arithmetic (no `eval()`) |
| `run_command(command, timeout_seconds=10)` | Run a whitelisted read-only shell command |

Plus one bonus MCP **resource** (`time://now`) showing that pattern too.

## 1. Install

```bash
cd mcp-utility-server
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Quick local test (no client needed)

The SDK ships a dev inspector UI:

```bash
mcp dev server.py
```

This opens a browser UI where you can call each tool manually and see
results — the fastest way to confirm everything works before wiring it
into a real client.

## 3. Wire it into Claude Desktop

Edit your Claude Desktop config file:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add an entry under `mcpServers` (create the file/key if it doesn't exist):

```json
{
  "mcpServers": {
    "utility-server": {
      "command": "/absolute/path/to/mcp-utility-server/.venv/bin/python",
      "args": ["/absolute/path/to/mcp-utility-server/server.py"]
    }
  }
}
```

Use **absolute paths** — relative paths and `~` are unreliable here.
Restart Claude Desktop. You should see a 🔨 tools icon indicating the
server connected, and the 5 tools available in chat.

## 4. Wire it into other clients

Any MCP client that supports stdio servers works the same way: point it
at the Python interpreter in `.venv` and `server.py` as the argument.
Claude Code, Cursor, and other MCP-aware tools use a similar
`command` + `args` config shape.

## Security notes (read this)

This server runs real code on your machine, so a few deliberate limits
are built in — widen them only if you understand the tradeoff:

- **`read_file` / `write_file`** are sandboxed to `~/mcp-sandbox` and
  will refuse any path that resolves outside it (blocks `../../etc/passwd`
  style escapes).
- **`run_command`** only allows a short allowlist of read-only commands
  (`ls`, `pwd`, `whoami`, `date`, `echo`, `cat`, `df`, `uname`). It does
  **not** run through a shell (`subprocess.run` with a list, not
  `shell=True`), so shell metacharacters (`;`, `&&`, `|`, backticks)
  don't do anything special — they're just treated as literal arguments.
- **`calculate`** parses the expression with `ast` and only allows
  numeric arithmetic — it never calls Python's `eval()`.
- **`fetch_url`** only allows `http(s)://` and has a 10s timeout.

If you want the file tools to reach outside the sandbox, or the shell
tool to run arbitrary commands, edit `BASE_DIR` / `ALLOWED_COMMANDS` in
`server.py` directly rather than removing the checks.

## Extending

Add a new tool by writing a plain Python function and decorating it:

```python
@mcp.tool()
def my_tool(x: int, y: str = "default") -> str:
    """One-line description the client/model sees.

    Args:
        x: what x is
        y: what y is
    """
    return f"{y}: {x}"
```

Type hints and the docstring are what the MCP client shows the model —
keep them accurate, since that's how the model decides when to call it.
