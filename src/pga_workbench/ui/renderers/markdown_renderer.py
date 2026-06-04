from __future__ import annotations


class MarkdownViewRenderer:
    def render(self, view: dict) -> str:
        return f"# {view.get('view_type', 'view')}\n\n{view.get('summary', '')}\n"
