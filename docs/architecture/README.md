# The phone edge's architecture pack

Open `index.html` (or `/docs/` on a running edge): the seven diagrams, what each one answers, and the review findings.

| | Diagram | Type |
|---|---|---|
| 01 | The phone, the edge and its backends | architecture |
| 02 | A phone joins, by USB or by QR | sequence |
| 03 | Events out, commands in | data flow |
| 04 | A profile, and what the edge keeps | data model (ERD) |
| 05 | One appliance into the inventory | sequence |
| 06 | A wall switch whose tiles follow the home | sequence |
| 07 | A backend stops reading (fixed in 23b2ca7) | sequence |

- `src/*.json`: the Archify sources. Each box cites repository lines at the commit in `meta.repository`.
- `*.html`: the rendered diagrams, standalone (open them from disk). `*.delivery.json`: their provenance.
- `receipts/summary.json`: the last build's gates per diagram; `receipts/<diagram>/` (git-ignored) each run's evidence.

Rebuild with `python3 build.py` (or `python3 build.py 03- 05-` for some). It needs Node.js 18+ and the Archify skill
(`~/.agents/skills/archify` or `~/.claude/skills/archify`). Archify checks every citation against the commit's bytes.

After a code change: commit the code, update the cited lines and `meta.repository.revision` in `src/` and `index.html`,
then rebuild and commit the pack on its own.

License: GPL-3.0-or-later.
