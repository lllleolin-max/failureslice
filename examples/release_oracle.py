"""Synthetic release-import fixture executing SQLite operations, not a claimed customer."""
import json
from pathlib import Path
import sqlite3
import sys
import time

TARGET = {"type": "sqlite3.IntegrityError", "message": "UNIQUE constraint failed: users.email", "operation": "duplicate-import"}
OTHER = {"type": "json.JSONDecodeError", "operation": "legacy-import"}


def emit(status, signature=None):
    result = {"status": status}
    if signature is not None:
        result["signature"] = signature
    print(json.dumps(result))
    return 0 if status == "PASS" else 1


def main():
    mode, candidate = sys.argv[1:3]
    if mode == "timeout":
        time.sleep(10)
    if mode == "overflow":
        sys.stdout.write("x" * 200000)
        sys.stdout.flush()
        time.sleep(10)
    if mode == "alternating":
        state = Path(sys.argv[3])
        count = int(state.read_text()) if state.exists() else 0
        state.write_text(str(count + 1))
        return emit("FAIL", TARGET) if count % 2 == 0 else emit("PASS")
    steps = json.loads(Path(candidate).read_text(encoding="utf-8"))["steps"]
    ids = {s["id"] for s in steps}
    if any(not set(s["requires"]) <= ids for s in steps):
        return emit("INVALID")
    if mode == "nonmonotone":
        return emit("FAIL", TARGET) if ids in ({"schema", "seed", "noise-a", "noise-b"}, {"schema", "seed"}) else emit("PASS")
    database = sqlite3.connect(":memory:")
    alternate = False
    try:
        for step in steps:
            operation = step["payload"].get("operation", step["id"])
            if operation == "schema":
                database.execute("CREATE TABLE users(email TEXT UNIQUE)")
            elif operation == "seed":
                database.execute("INSERT INTO users VALUES ('fixture@example.invalid')")
            elif operation == "duplicate-import":
                try:
                    database.execute("INSERT INTO users VALUES ('fixture@example.invalid')")
                except sqlite3.IntegrityError:
                    return emit("FAIL", TARGET)
            elif operation == "legacy-import" and mode != "standard-success":
                try:
                    json.loads("{")
                except json.JSONDecodeError:
                    alternate = True
        return emit("FAIL", OTHER) if alternate else emit("PASS")
    except sqlite3.Error:
        return emit("INVALID")
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
