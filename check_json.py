import json, pathlib

p = pathlib.Path("bowlers.json").read_text(encoding="utf-8")

try:
    json.loads(p)
    print("✅ JSON is valid.")
except json.JSONDecodeError as e:
    print(f"❌ {e}")
    i = e.pos  # character index
    start = max(0, i - 200)
    end = min(len(p), i + 200)
    snippet = p[start:end]
    # Show line/col and a caret to the char position
    print("\n--- context ---")
    print(snippet)
    print(" " * (i - start) + "^")