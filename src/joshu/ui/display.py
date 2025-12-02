from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

height = 10
joshu_logo = """
   ⣴⣶⣤⡤  ⠦⡀⠳⢀⣠⡴⠂⠲⣴⣶⣄⡀    ⣶⣶  ⣶⣶  ⣴⣶⣤⡤  ⣶⣶⣶⣶  ⣶⣶
   ⢸⣶⣤⣤⡤  ⠧⠘ ⠳⢦⡀⠁ ⠸⣶⣤⣀⡀   ⢸⣿⣿  ⣿⣿⣿  ⢸⣶⣤⣤⡤  ⣿⣿⣿⣿  ⣿⣿
   ⢸⣿⣿⣿⡿  ⠘ ⡀ ⢀⣠⠴⠚ ⢸⣿⣿⣿⡿   ⢸⣿   ⣿   ⢸⣿⣿⣿⡿  ⣿⣿  ⣿⣿  ⣿⣿
   ⠘⣿⣿⣿⣿  ⠘ ⠁⠈⢸⣴⡀ ⠘⣿⣿⣿⣿   ⢸⣿   ⣿   ⢸⣿⣿⣿⣿  ⣿⣿  ⣿⣿  ⣿⣿
   ⣀⣿⣿⣿⡿  ⢀ ⣠⠴⠚ ⢸⣿⣿⣿⣿⡿⠘   ⢸⣿   ⣿   ⣠⣿⣿⣿⡿  ⣿⣿  ⣿⣿  ⣿⣿
   ⣠⣿⣿⡿⠿  ⣠⠂⠔⠢⣀⣀⣿⣿⣿⡿⠻⠘  ⢸⣿   ⣿   ⣠⣿⣿⡿⠿  ⣿⣿  ⣿⣿  ⣿⣿
   ⣿⣿⣿⡟⠁  ⣿⠆ ⠈⠛⠻⢦⣷⣿⣿⣿⠟⠁  ⢸⣿   ⣿   ⣿⣿⣿⡟⠁  ⣿⣿  ⣿⣿  ⣿⣿
   ⣿⣿⣿⠟⠁  ⣿⠾ ⠿⠟⠛⠒⠂⣸⣿⣿⣿⠁  ⢸⣿   ⣿   ⣿⣿⣿⠟⠁  ⣿⣿  ⣿⣿  ⣿⣿
   ⣿⣿⣿⠃⠁  ⣿ ⠊ ⠉⠉⠁⠠⠴⣿⣿⣿⠃⠁  ⢸⣿   ⣿   ⣿⣿⣿⠃⠁  ⣿⣿  ⣿⣿  ⣿⣿
   ⣿⣿⠁⠁⠁  ⠸⠁ ⠈⠉⠉⠁⠄⣿⣿⣿⠁⠁   ⠈⠉   ⠈    ⣿⣿⠁⠁⠁  ⠈⠉  ⠈⠉  ⠈⠉
   ⠈⠉⠉⠉⠁  ⠠ ⠈ ⠉⠉⠁⠄⣿⣿⠁⠁⠁       ⠀⠀⠀⠀⠀   ⠈⠉⠉⠉⠁
"""


def get_colored_logo():
    """Return a colored version of the JOSHU logo"""
    logo_text = Text()
    logo_text.append(joshu_logo, style="bold blue")
    return logo_text


def print_banner(model_name: str) -> None:
    # Create usage tips
    tips = Text()
    tips.append("1. Ask questions, edit files, or run commands.\n", style="dim")
    tips.append("2. Be specific for the best results.\n", style="dim")
    tips.append(
        "3. Create JOSHU.md files to customize your interactions with Joshu.\n", style="dim"
    )
    tips.append("4. /help for more information.", style="dim")

    # Create the panel with colored ASCII art as title
    banner = Panel.fit(tips, title=get_colored_logo(), title_align="center", border_style="blue")
    console.print(banner)
