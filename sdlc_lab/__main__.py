import sys
from .workflow import run_demo

if __name__ == "__main__":
    is_interactive = "--auto" not in sys.argv
    run_demo(interactive=is_interactive)
