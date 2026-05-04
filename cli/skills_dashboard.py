"""Textual TUI Dashboard for Skills Manager.

Real-time dashboard that monitors skills-index.json and provides
an interactive interface for browsing, searching, and managing skills.

Panels:
  (a) Skills Overview - Total count, category distribution
  (b) Skills Browser - Browse skills by category
  (c) Search Results - Search results display
  (d) Details Panel - Selected skill details
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from threading import Lock, Timer

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Input, RichLog, Static, Tree
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

SKILLS_ROOT = Path(__file__).parent.parent
INDEX_PATH = SKILLS_ROOT / "skills-index.json"
SCRUM_DIR = SKILLS_ROOT / ".skills"

CATEGORIES_EMOJI = {
    "product": "🔵", "agile": "🟢", "scrum": "🟡", "ddd": "🟠",
    "dev-quality": "🟣", "qa-testing": "🔴", "api-design": "⚪",
    "ai-product": "🩵", "ai-safety": "🚨", "superpowers": "⚡",
    "dev-workflow": "🔧", "design": "🎨", "skill-authoring": "🛠️", "indie-hacker": "💰"
}

CATEGORIES_COLOR = {
    "product": "blue", "agile": "green", "scrum": "yellow", "ddd": "orange",
    "dev-quality": "magenta", "qa-testing": "red", "api-design": "white",
    "ai-product": "cyan", "ai-safety": "red", "superpowers": "yellow",
    "dev-workflow": "cyan", "design": "magenta", "skill-authoring": "cyan", "indie-hacker": "yellow"
}


def read_json(path: Path) -> dict | list | None:
    """Read a JSON file, returning None if missing or invalid."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return None


class SkillsOverview(Static):
    """Panel (a): Skills overview with total count and category distribution."""

    DEFAULT_CSS = """
    SkillsOverview {
        height: auto;
        min-height: 8;
        border: solid $accent;
        padding: 0 1;
    }
    """

    def update_content(self) -> None:
        index = read_json(INDEX_PATH)
        if not index:
            self.update("[bold]No skills index found[/bold]\nRun build_skills_index.py to create.")
            return

        total = index.get("total_count", 0)
        by_category = index.get("by_category", {})

        lines = [f"[bold cyan]🧠 Skills Manager Dashboard[/bold cyan]"]
        lines.append(f"[bold]Total Skills:[/bold] {total}")
        lines.append("")
        lines.append("[bold]Category Distribution:[/bold]")

        sorted_cats = sorted(by_category.items(), key=lambda x: -len(x[1].get("skills", [])))

        for cat_key, cat_info in sorted_cats:
            emoji = CATEGORIES_EMOJI.get(cat_key, "⚪")
            count = len(cat_info.get("skills", []))
            bar = "█" * min(count, 20)
            color = CATEGORIES_COLOR.get(cat_key, "white")
            lines.append(f"  {emoji} [{color}]{cat_key:<15}[/{color}] {bar} {count}")

        lines.append("")
        lines.append("[dim]Press ? for keyboard shortcuts[/dim]")

        self.update("\n".join(lines))


class CategoryTree(Tree):
    """Panel (b): Category tree for browsing skills."""

    DEFAULT_CSS = """
    CategoryTree {
        height: 1fr;
        border: solid $accent;
    }
    """

    def __init__(self, **kwargs):
        super().__init__("📂 Skills Browser", **kwargs)

    def on_mount(self) -> None:
        self.show_root = False
        self.update_content()

    def update_content(self) -> None:
        index = read_json(INDEX_PATH)
        if not index:
            return

        self.clear()
        by_category = index.get("by_category", {})

        for cat_key, cat_info in sorted(by_category.items()):
            emoji = CATEGORIES_EMOJI.get(cat_key, "⚪")
            cat_node = self.root.add(f"{emoji} {cat_info['name']}", data={"type": "category", "key": cat_key})

            for skill in cat_info.get("skills", []):
                skill_name = skill.get("name", "unknown")
                cat_node.add(f"  📄 {skill_name}", data={"type": "skill", "key": skill_name, "data": skill})

        if self.root.children:
            for child in self.root.children:
                child.expand = True


class SearchInput(Input):
    """Search input widget."""

    DEFAULT_CSS = """
    SearchInput {
        height: 3;
        border: solid $accent;
        margin: 1 0;
    }
    """

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.app.search_skills(event.value)


class SkillsDetail(Static):
    """Panel (d): Selected skill details."""

    DEFAULT_CSS = """
    SkillsDetail {
        height: 1fr;
        border: solid $accent;
        padding: 0 1;
    }
    """

    def update_content(self, skill: dict | None) -> None:
        if not skill:
            self.update("[dim]Select a skill to view details[/dim]")
            return

        lines = [f"[bold cyan]📄 {skill.get('name', 'Unknown')}[/bold cyan]"]
        lines.append("")

        emoji = CATEGORIES_EMOJI.get(skill.get("category_key", ""), "📦")
        lines.append(f"[bold]Category:[/bold] {emoji} {skill.get('category_name', 'N/A')}")

        desc = skill.get("description", "No description")
        lines.append(f"[bold]Description:[/bold] {desc}")

        purpose = skill.get("purpose", "")
        if purpose:
            lines.append("")
            lines.append("[bold]Purpose:[/bold]")
            lines.append(purpose[:300] + "..." if len(purpose) > 300 else purpose)

        path = skill.get("path", "")
        lines.append("")
        lines.append(f"[bold]Path:[/bold] {path}")

        self.update("\n".join(lines))


class SkillsDashboard(App):
    """Main Textual TUI dashboard application."""

    TITLE = "🧠 Skills Manager Dashboard"
    CSS = """
    Screen {
        layout: grid;
        grid-size: 2 1;
        grid-columns: 1fr 1fr;
        grid-rows: auto 1fr auto;
    }
    #overview {
        column-span: 2;
    }
    #search-row {
        column-span: 2;
        height: 3;
    }
    #browser {
        row-span: 2;
    }
    #detail {
        row-span: 2;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "focus_search", "Search"),
        Binding("b", "focus_browser", "Browse"),
        Binding("?", "show_help", "Help"),
        Binding("escape", "clear_selection", "Clear"),
    ]

    def __init__(self):
        super().__init__()
        self.selected_skill = None
        self.search_results = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield SkillsOverview(id="overview")
        yield SearchInput(placeholder="🔍 Search skills (press Enter)...", id="search-input")
        yield Vertical(
            Static("[bold]📂 Skills Browser[/bold]"), CategoryTree(id="category-tree"), id="browser"
        )
        yield Vertical(
            Static("[bold]📄 Skill Details[/bold]"), SkillsDetail(id="skill-detail"), id="detail"
        )
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_panels()
        self._start_watcher()
        self.set_interval(5, self.refresh_panels)

    def _start_watcher(self) -> None:
        """Start watchdog observer for skills directory."""
        if not SCRUM_DIR.exists():
            SCRUM_DIR.mkdir(parents=True, exist_ok=True)

        watch_path = str(SKILLS_ROOT.resolve())

        self._observer = Observer()
        self._observer.schedule(
            SkillsFileHandler(self), watch_path, recursive=True
        )
        self._observer.daemon = True
        self._observer.start()

    def refresh_panels(self) -> None:
        """Refresh all dashboard panels from disk."""
        overview = self.query_one("#overview", SkillsOverview)
        overview.update_content()

        tree = self.query_one("#category-tree", CategoryTree)
        tree.update_content()

        detail = self.query_one("#skill-detail", SkillsDetail)
        detail.update_content(self.selected_skill)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        node_data = event.node.data
        if node_data and node_data.get("type") == "skill":
            self.selected_skill = node_data.get("data")
            detail = self.query_one("#skill-detail", SkillsDetail)
            detail.update_content(self.selected_skill)

    def search_skills(self, query: str) -> None:
        """Search skills and display results."""
        if not query:
            return

        index = read_json(INDEX_PATH)
        if not index:
            return

        query_lower = query.lower()
        results = []

        for cat_key, cat_info in index.get("by_category", {}).items():
            for skill in cat_info.get("skills", []):
                name = skill.get("name", "").lower()
                desc = skill.get("description", "").lower()

                if query_lower in name or query_lower in desc:
                    skill["category_key"] = cat_key
                    skill["category_name"] = cat_info["name"]
                    results.append(skill)

        self.search_results = results

        tree = self.query_one("#category-tree", CategoryTree)
        tree.clear()

        if results:
            result_root = tree.root.add(f"🔍 Search Results ({len(results)})", data={"type": "category", "key": "results"})
            for skill in results:
                emoji = CATEGORIES_EMOJI.get(skill.get("category_key", ""), "📦")
                result_root.add(f"  {emoji} {skill.get('name', 'unknown')}", data={"type": "skill", "key": skill.get("name"), "data": skill})
            result_root.expand = True
        else:
            tree.root.add(f"🔍 No results for '{query}'")

    def action_refresh(self) -> None:
        self.refresh_panels()

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_focus_browser(self) -> None:
        self.query_one("#category-tree", CategoryTree).focus()

    def action_show_help(self) -> None:
        help_text = """
[bold cyan]🧠 Skills Manager Dashboard - Keyboard Shortcuts[/bold cyan]

  [bold]q[/bold] - Quit
  [bold]r[/bold] - Refresh panels
  [bold]s[/bold] - Focus search input
  [bold]b[/bold] - Focus skills browser
  [bold]?[/bold] - Show this help
  [bold]Esc[/bold] - Clear selection

[bold]Navigation:[/bold]
  Use Tab to switch between panels
  Use arrow keys to navigate tree
  Press Enter to select a skill
"""
        self.push_screen(HelpScreen(help_text))

    def action_clear_selection(self) -> None:
        self.selected_skill = None
        self.refresh_panels()

    def on_unmount(self) -> None:
        if hasattr(self, "_observer"):
            self._observer.stop()
            self._observer.join(timeout=2)


class HelpScreen(Static):
    """Help overlay screen."""

    def __init__(self, text: str):
        super().__init__(text)
        self.styles.width = "60%"
        self.styles.height = "auto"
        self.styles.background = "darkblue"
        self.styles.padding = 2


class SkillsFileHandler(FileSystemEventHandler):
    """Watchdog handler that triggers debounced dashboard updates."""

    DEBOUNCE_SECONDS = 0.5

    def __init__(self, app: SkillsDashboard) -> None:
        super().__init__()
        self.app = app
        self._lock = Lock()
        self._pending_timer: object | None = None

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        self._schedule_update()

    def on_created(self, event) -> None:
        if event.is_directory:
            return
        self._schedule_update()

    def _schedule_update(self) -> None:
        with self._lock:
            if self._pending_timer is not None:
                self._pending_timer.cancel()
            self._pending_timer = Timer(
                self.DEBOUNCE_SECONDS,
                lambda: self.app.call_from_thread(self.app.refresh_panels),
            )
            self._pending_timer.daemon = True
            self._pending_timer.start()


if __name__ == "__main__":
    app = SkillsDashboard()
    app.run()
