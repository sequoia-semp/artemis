from __future__ import annotations

from pga_workbench.ui.renderers.json_renderer import JsonViewRenderer
from pga_workbench.ui.renderers.markdown_renderer import MarkdownViewRenderer


def test_view_renderers_smoke():
    view = {"view_type": "current_day", "summary": "test"}

    assert '"view_type": "current_day"' in JsonViewRenderer().render(view)
    assert "# current_day" in MarkdownViewRenderer().render(view)
