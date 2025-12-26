from pathlib import Path
import json


RESULTS_ROOT = Path() / "results"


for result_file in RESULTS_ROOT.glob("锂电网_*.json"):
    ...