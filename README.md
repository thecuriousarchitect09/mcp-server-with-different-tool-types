# Local Utility MCP Server

A minimal, local Python MCP server exposing 5 general-purpose tools, built
with the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
(`FastMCP`).

## 1. Install

```bash
cd mcp-server-with-different-tool-types
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Quick local test (no client needed)

The SDK ships a dev inspector UI:

```bash
python server.py
```

This opens a browser UI where you can call each tool manually and see
results — the fastest way to confirm everything works before wiring it
into a real client.

# MCP Server — Tools, Resources & Prompts

A simple **Model Context Protocol (MCP) server built with Python** that demonstrates the core MCP concepts:

* 🔧 **Tools** — perform actions
* 📦 **Resources** — expose data
* 🔗 **Resource Templates** — dynamically expose data using URI parameters
* 💬 **Prompts** — provide reusable instructions
* 🔄 **JSON-RPC** — the protocol message format underneath MCP

This project is designed as a simple starting point for understanding **what actually happens inside an MCP server**.

---

## 🏗️ What This Server Demonstrates

```text
                     MCP SERVER
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
        TOOLS         RESOURCES       PROMPTS
          │              │              │
          ▼              ▼              ▼
        add()       demo://greeting   explain_topic()
          │              │              │
          ▼              ▼              ▼
        ACTION          DATA        INSTRUCTION
```

### Tools

The server exposes an `add` tool:

```python
add(a, b)
```

Example:

```text
add(10, 20)
→ 30
```

MCP clients discover tools using:

```text
tools/list
```

and invoke them using:

```text
tools/call
```

---

### Resources

The server exposes a static resource:

```text
demo://greeting
```

Reading this resource returns:

```text
Hello from my MCP server!
```

Resources are discovered using:

```text
resources/list
```

and read using:

```text
resources/read
```

---

### Resource Templates

The server also demonstrates a dynamic resource:

```text
demo://user/{name}
```

For example:

```text
demo://user/alice
```

returns:

```text
User name: alice
Status: Active
```

This demonstrates how MCP resource templates can expose dynamically generated data through URI parameters.

---

### Prompts

The server exposes a reusable prompt:

```text
explain_topic
```

For example:

```text
explain_topic("MCP")
```

generates a structured instruction asking an AI model to explain MCP in simple terms.

Prompts are discovered using:

```text
prompts/list
```

and retrieved using:

```text
prompts/get
```

---

# 🔄 MCP JSON-RPC Flow

MCP uses **JSON-RPC** messages to communicate between the client and server.

For example, to discover available tools:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list"
}
```

To call the `add` tool:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "add",
    "arguments": {
      "a": 10,
      "b": 20
    }
  }
}
```

The important idea is:

```text
JSON-RPC
   ↓
Message format

MCP
   ↓
Defines what the messages mean

tools/list
tools/call
resources/list
resources/read
prompts/list
prompts/get
   ↓
MCP operations
```

---

# 🧠 MCP Concepts at a Glance

| Concept           | Purpose               | Example              |
| ----------------- | --------------------- | -------------------- |
| Tool              | Perform an action     | `add()`              |
| Resource          | Expose data           | `demo://greeting`    |
| Resource Template | Dynamic data          | `demo://user/{name}` |
| Prompt            | Reusable instructions | `explain_topic()`    |
| JSON-RPC          | Communication format  | `tools/call`         |

---

