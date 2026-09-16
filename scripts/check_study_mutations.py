"""Prüft, dass die neuen Regressionstests gezielt eingebaute Fehler erkennen.

Die Mutationen leben nur im Speicher separater Python-Prozesse. Quellcode,
Referenzdateien und Modellgewichte werden nicht verändert.
"""

import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    mutations = {
        "falscher Endindex": """
import pytest
from magda import semeval
original = semeval._convert
def broken_convert(pages):
    return [[{**span, 'end': span['end'] + 1} for span in page] for page in original(pages)]
semeval._convert = broken_convert
raise SystemExit(pytest.main(['-q', 'tests/test_semeval.py::test_benachbarte_einwortspans_ueberlappen_nicht']))
""",
        "festgehaltene Bootstrap-Ziehungen": """
import pytest
import numpy as np
from types import SimpleNamespace
from magda import resampling
def broken_rng(seed):
    return SimpleNamespace(multinomial=lambda count, probabilities, size: np.tile([count] + [0] * (len(probabilities) - 1), (size, 1)))
resampling.np.random.default_rng = broken_rng
raise SystemExit(pytest.main(['-q', 'tests/test_resampling.py::test_micro_f1_wird_aus_zaehlern_statt_seitenmittel_berechnet']))
""",
        "ungefragte Annotationsaufgabe": """
import argparse
from pathlib import Path
import pytest
original = argparse.ArgumentParser.parse_args
def broken_parse(self, *args, **kwargs):
    args = original(self, *args, **kwargs)
    if hasattr(args, 'review_packet'):
        args.review_packet = Path('unexpected-review')
    return args
argparse.ArgumentParser.parse_args = broken_parse
raise SystemExit(pytest.main(['-q', 'tests/test_study_scope.py::test_studienabschluss_erzeugt_keine_neue_annotationsaufgabe']))
""",
        "ignorierte Quellenänderung nach Commit": """
import inspect
import pytest
from magda import evaluation_study
code = inspect.getsource(evaluation_study.verify_snapshot).replace(
    'current_code["source_sha256"] != study["code"]["source_sha256"]', 'False')
exec(code, evaluation_study.__dict__)
raise SystemExit(pytest.main(['-q', 'tests/test_study_scope.py::test_report_pruefung_erlaubt_neuen_commit_aber_keine_neuen_quellen']))
""",
    }
    for name, code in mutations.items():
        result = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True)
        if result.returncode != 1 or "1 failed" not in result.stdout:
            print(result.stdout, result.stderr)
            raise SystemExit(f"Mutation nicht zuverlässig erkannt: {name}")
        print(f"Regressionstest wird erwartungsgemäß rot: {name}")


if __name__ == "__main__":
    main()
