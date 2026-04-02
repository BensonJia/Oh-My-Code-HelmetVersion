---
name: customize-response-style
description: Guide for customizing OhMyCode's terminal output style and rendering. Use when user wants to change colors, formatting, or how responses look in the terminal.
---

# Customize OhMyCode's Response Style

Change how OhMyCode renders output in the terminal — colors, formatting, tool call display, token usage display.

## When to Use

- User says "change the colors", "make output cleaner", "customize the theme"
- User wants to modify how tool calls, errors, or streaming text are displayed
- User wants to add/remove elements from the output (e.g., hide token counts)

## Where Rendering Happens

All rendering logic is in `ohmycode/cli.py` → `render_stream()` function. It consumes events from the conversation loop and prints them using `rich.console.Console`.

Current rendering:

| Event | Current Style |
|-------|--------------|
| `TextChunk` | Plain text, streamed character by character |
| `ToolCallStart` | `▶ <tool_name>` in cyan + params in dim |
| `ToolCallResult` (success) | `✓` + green output (truncated to 500 chars) |
| `ToolCallResult` (error) | `✗` + red error message |
| `TurnComplete` | `Tokens: prompt=X completion=Y total=Z` in dim |

## How to Customize

### Option 1: Edit render_stream() Directly

Open `ohmycode/cli.py` and find `async def render_stream()`. Modify the rich markup:

```python
# Change tool call header color from cyan to blue
console.print(f"\n[blue]▶ {event.tool_name}[/blue]", highlight=False)

# Add a box around tool results
from rich.panel import Panel
console.print(Panel(output, title="Tool Result", border_style="green"))

# Hide token usage
# Comment out or delete the TurnComplete rendering block
```

### Option 2: Add Rich Themes

Create a custom theme at the top of `cli.py`:

```python
from rich.theme import Theme

ohmycode_theme = Theme({
    "tool.name": "bold magenta",
    "tool.success": "green",
    "tool.error": "bold red",
    "tool.params": "dim italic",
    "status": "dim cyan",
    "prompt": "bold yellow",
})

console = Console(theme=ohmycode_theme)
```

Then use style names in print calls:

```python
console.print(f"▶ {event.tool_name}", style="tool.name")
```

### Option 3: Add Markdown Rendering for AI Responses

Replace plain text streaming with rich Markdown rendering:

```python
from rich.markdown import Markdown

# In render_stream(), after collecting all TextChunks for a turn:
if collected_text:
    console.print(Markdown(collected_text))
```

**Trade-off:** Markdown rendering requires buffering the full response (no streaming feel). A hybrid approach: stream plain text, then re-render as Markdown after the turn completes.

### Option 4: Customize the REPL Prompt

In `run_repl()`, change the prompt appearance:

```python
# Simple change
user_input = session.prompt("ohmycode> ")

# With color (prompt_toolkit style)
from prompt_toolkit.formatted_text import HTML
user_input = session.prompt(HTML("<ansigreen>ohmycode</ansigreen><ansiyellow>></ansiyellow> "))

# With model name
user_input = session.prompt(f"[{config.model}]> ")
```

## Customization Ideas

| Change | Where | Difficulty |
|--------|-------|-----------|
| Change colors | `render_stream()` rich markup | Easy |
| Add panels/borders around tool results | `render_stream()` + `rich.Panel` | Easy |
| Show full tool params (not truncated) | `render_stream()` truncation logic | Easy |
| Hide token usage | `render_stream()` TurnComplete block | Easy |
| Add timestamps to output | `render_stream()` | Easy |
| Markdown rendering | `render_stream()` + `rich.Markdown` | Medium |
| Custom REPL prompt | `run_repl()` prompt_toolkit config | Medium |
| Add spinner during tool execution | `render_stream()` + `rich.Status` | Medium |
| Progress bar for long operations | `render_stream()` + `rich.Progress` | Medium |
| Split-pane layout (output + status) | `rich.Layout` | Hard |

## Testing Changes

After modifying `cli.py`:

1. Quick visual test: `ohmycode -p "List python files here" --mode auto`
2. Test tool calls: `ohmycode -p "Read pyproject.toml" --mode auto`
3. Test errors: `ohmycode -p "Read /nonexistent/file" --mode auto`
4. Test REPL: `ohmycode` → type a message → `/exit`

## Tips

- Use `rich` documentation: https://rich.readthedocs.io/
- Preview colors: `python3 -c "from rich import print; print('[bold red]Red[/bold red] [green]Green[/green]')"`
- Keep changes in `render_stream()` — don't modify `core/loop.py` for display concerns
- The REPL prompt uses `prompt_toolkit`, not `rich` — they have different styling systems
