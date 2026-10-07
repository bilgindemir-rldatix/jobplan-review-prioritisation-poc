import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from jobplan_poc.dashboard import main  # noqa: E402

main()
