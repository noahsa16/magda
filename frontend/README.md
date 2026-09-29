# Magda Weboberfläche

React, TypeScript und Vite. Zeigt Prospekte, Annotationen und Modellvergleiche.
Installation und gemeinsamer Start von API und Oberfläche: [Projekt-README](../README.md).

Für die Frontend-Entwicklung aus dem Projektroot:

```bash
npm --prefix frontend ci
.venv/bin/magda serve
```

In einem zweiten Terminal:

```bash
npm --prefix frontend run dev
```

Vite leitet `/api` an `http://localhost:8000` weiter.
Für ein anderes Backend `MAGDA_API` setzen.

```bash
npm --prefix frontend test
npm --prefix frontend run build
```
