# Windows entry point for desktop shell
import sys
import os

# Add project root to path for embedded Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ttcopy.desktop_shell import main

if __name__ == "__main__":
    main()
