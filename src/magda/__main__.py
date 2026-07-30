"""`python -m magda` – derselbe Einstieg wie der installierte Befehl `magda`.

Der Runner ruft die Schritte so auf, weil `config.PYTHON` dort explizit auf das
Projekt-venv zeigt. Über den Konsolenbefehl ginge das nicht: welches `magda`
im PATH liegt, hängt an der Umgebung, aus der die API gestartet wurde.
"""

from magda.cli import main

raise SystemExit(main())
