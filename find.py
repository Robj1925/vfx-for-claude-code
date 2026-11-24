#!/usr/bin/env python3
"""Find an effect in the library by any word: id, name, alias, look, use or mood.

  python3 find.py glow            # -> T01 Light leak glow transition
  python3 find.py "step in"       # -> T02
  python3 find.py title           # every title effect
  python3 find.py --all           # the whole catalog
  python3 find.py glitch --open   # also opens the demo GIF
"""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_all, do_open = "--all" in sys.argv, "--open" in sys.argv
    cat = json.loads((HERE / "catalog.json").read_text())["effects"]
    q = " ".join(args).lower()
    hits = []
    for e in cat:
        hay = " ".join([e["id"], e["name"], e["kind"], e["look"], e["use_for"], " ".join(e["aliases"]),
                        " ".join(e.get("mood", [])), " ".join(e.get("looks", []))]).lower()
        if show_all or (q and all(w in hay for w in q.split())):
            hits.append(e)
    if not hits:
        print(f"no effect matches '{q}'. Try: python3 find.py --all")
        return
    for e in hits:
        print(f"{e['id']}  {e['name']}  ({e['kind']}, {str(e['frames']) + ' frames' if e['frames'] else 'any length'})")
        print(f"  look: {e['look']}")
        print(f"  use:  {e['use_for']}")
        print(f"  run:  {e['command']}")
        print(f"  demo: {', '.join(str(HERE / d) for d in e['demo'])}")
        print()
        if do_open:
            subprocess.run(["open", str(HERE / e["demo"][0])])


if __name__ == "__main__":
    main()
