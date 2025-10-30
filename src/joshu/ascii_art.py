# joshu/ascii_art.py

from rich.text import Text

height = 10
joshu_logo = """
   ⣴⣶⣤⡤  ⠦⡀⠳⢀⣠⡴⠂⠲⣴⣶⣄⡀
   ⢸⣶⣤⣤⡤  ⠧⠘ ⠳⢦⡀⠁ ⠸⣶⣤⣀⡀
   ⢸⣿⣿⣿⡿  ⠘ ⡀ ⢀⣠⠴⠚ ⢸⣿⣿⣿⡿
   ⠘⣿⣿⣿⣿  ⠘ ⠁⠈⢸⣴⡀ ⠘⣿⣿⣿⣿
   ⣀⣿⣿⣿⡿  ⢀ ⣠⠴⠚ ⢸⣿⣿⣿⣿⡿⠘
   ⣠⣿⣿⡿⠿  ⣠⠂⠔⠢⣀⣀⣿⣿⣿⡿⠻⠘
   ⣿⣿⣿⡟⠁  ⣿⠆ ⠈⠛⠻⢦⣷⣿⣿⣿⠟⠁
   ⣿⣿⣿⠟⠁  ⣿⠾ ⠿⠟⠛⠒⠂⣸⣿⣿⣿⠁
   ⣿⣿⣿⠃⠁  ⣿ ⠊ ⠉⠉⠁⠠⠴⣿⣿⣿⠃⠁
   ⣿⣿⠁⠁⠁  ⠸⠁ ⠈⠉⠉⠁⠄⣿⣿⣿⠁⠁
   ⠈⠉⠉⠉⠁  ⠠ ⠈ ⠉⠉⠁⠄⣿⣿⠁⠁⠁
"""

def get_colored_logo():
    """Return a colored version of the JOSHU logo"""
    logo_text = Text()
    logo_text.append(joshu_logo, style="bold blue")
    return logo_text