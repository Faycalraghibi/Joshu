from __future__ import annotations

from rich.panel import Panel
from rich.console import Console
from rich.text import Text
from rich.align import Align

console = Console()


# def print_banner(model_name: str) -> None:
#     # Create pixel-style JOSHU title
#     joshu_text = Text()
#     joshu_text.append("J", style="bold red")
#     joshu_text.append("O", style="bold yellow")
#     joshu_text.append("S", style="bold green")
#     joshu_text.append("H", style="bold cyan")
#     joshu_text.append("U", style="bold blue")
    
#     # Create usage tips
#     tips = Text()
#     tips.append("1. Ask questions, edit files, or run commands.\n", style="dim")
#     tips.append("2. Be specific for the best results.\n", style="dim")
#     tips.append("3. Create JOSHU.md files to customize your interactions with Joshu.\n", style="dim")
#     tips.append("4. /help for more information.", style="dim")
    
#     # Create the panel with the title as a Text object
#     banner = Panel.fit(
#         tips,
#         title=joshu_text,
#         title_align="center",
#         border_style="blue"
#     )
#     console.print(banner)

from joshu.ascii_art import get_colored_logo

def print_banner(model_name: str) -> None:
    # Create usage tips
    tips = Text()
    tips.append("1. Ask questions, edit files, or run commands.\n", style="dim")
    tips.append("2. Be specific for the best results.\n", style="dim")
    tips.append("3. Create JOSHU.md files to customize your interactions with Joshu.\n", style="dim")
    tips.append("4. /help for more information.", style="dim")
    
    # Create the panel with colored ASCII art as title
    banner = Panel.fit(
        tips,
        title=get_colored_logo(),
        title_align="center",
        border_style="blue"
    )
    console.print(banner)