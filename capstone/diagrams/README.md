# Diagrams

Exported images are here. Editable sources are in `src/` (Graphviz).

| File | What |
|---|---|
| `c4-l1-context.svg` | C4 Level 1: who uses Hesal and which systems it talks to |
| `c4-l2-containers.svg` | C4 Level 2: the parts inside Hesal |

To redraw after editing a source:

    dot -Tsvg src/c4-l1-context.dot -o c4-l1-context.svg
