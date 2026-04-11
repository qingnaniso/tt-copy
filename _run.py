import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ttcopy.main import main
import asyncio
asyncio.run(main())
