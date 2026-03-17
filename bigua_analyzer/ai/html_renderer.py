"""Convert a Markdown string to a self-contained HTML document."""
from __future__ import annotations

from pathlib import Path


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                   Helvetica, Arial, sans-serif;
      max-width: 860px;
      margin: 40px auto;
      padding: 0 20px;
      line-height: 1.7;
      color: #222;
    }}
    h1 {{ border-bottom: 2px solid #0366d6; padding-bottom: 0.3em; }}
    h2 {{ border-bottom: 1px solid #e1e4e8; padding-bottom: 0.2em; margin-top: 2em; }}
    code {{ background: #f6f8fa; padding: 0.2em 0.4em; border-radius: 3px; }}
    pre code {{ background: none; padding: 0; }}
    pre {{
      background: #f6f8fa;
      padding: 1em;
      border-radius: 6px;
      overflow-x: auto;
    }}
    blockquote {{
      border-left: 4px solid #0366d6;
      margin: 0;
      padding: 0 1em;
      color: #555;
    }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #e1e4e8; padding: 8px 12px; text-align: left; }}
    th {{ background: #f6f8fa; }}
  </style>
</head>
<body>
{body}
</body>
</html>
"""


def _markdown_to_html_body(markdown_text: str) -> tuple[str, str]:
    """
    Convert Markdown to an HTML body fragment.

    Prefers the 'markdown' package if available, falls back to 'mistune',
    and finally to a minimal built-in converter that handles headings,
    bold, italic, inline code, and paragraphs — enough for LLM report output.
    """
    try:
        import markdown  # type: ignore

        body = markdown.markdown(
            markdown_text,
            extensions=["tables", "fenced_code"],
        )
        # Derive title from first H1
        title = _extract_title(markdown_text)
        return title, body
    except ImportError:
        pass

    try:
        import mistune  # type: ignore

        body = mistune.html(markdown_text)
        title = _extract_title(markdown_text)
        return title, body
    except ImportError:
        pass

    # Minimal built-in fallback
    return _extract_title(markdown_text), _builtin_md_to_html(markdown_text)


def _extract_title(markdown_text: str) -> str:
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return "Repository Analysis Report"


def _builtin_md_to_html(text: str) -> str:
    """Very small subset of Markdown -> HTML, sufficient for report output."""
    import re
    import html as html_module

    lines = text.splitlines()
    output: list[str] = []
    in_pre = False
    para: list[str] = []

    def flush_para() -> None:
        if para:
            content = " ".join(para).strip()
            if content:
                output.append(f"<p>{content}</p>")
            para.clear()

    for line in lines:
        # Fenced code blocks
        if line.startswith("```"):
            if in_pre:
                output.append("</code></pre>")
                in_pre = False
            else:
                flush_para()
                output.append("<pre><code>")
                in_pre = True
            continue
        if in_pre:
            output.append(html_module.escape(line))
            continue

        # ATX headings
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            flush_para()
            level = len(m.group(1))
            content = _inline_md(m.group(2))
            output.append(f"<h{level}>{content}</h{level}>")
            continue

        # Horizontal rule
        if re.match(r"^[-*_]{3,}\s*$", line):
            flush_para()
            output.append("<hr />")
            continue

        # Unordered list item
        m = re.match(r"^[-*+]\s+(.*)", line)
        if m:
            flush_para()
            output.append(f"<ul><li>{_inline_md(m.group(1))}</li></ul>")
            continue

        # Ordered list item
        m = re.match(r"^\d+\.\s+(.*)", line)
        if m:
            flush_para()
            output.append(f"<ol><li>{_inline_md(m.group(1))}</li></ol>")
            continue

        # Blank line ends paragraph
        if not line.strip():
            flush_para()
            continue

        para.append(_inline_md(line))

    flush_para()
    return "\n".join(output)


def _inline_md(text: str) -> str:
    import re
    import html as html_module

    text = html_module.escape(text, quote=False)
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)
    # Inline code
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    # Links
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def render_html(markdown_text: str, output_path: Path) -> None:
    """Render *markdown_text* as HTML and write to *output_path*."""
    title, body = _markdown_to_html_body(markdown_text)
    html = _HTML_TEMPLATE.format(title=title, body=body)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
