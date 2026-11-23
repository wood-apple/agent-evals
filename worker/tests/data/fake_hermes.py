#!/usr/bin/env python3
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

args = sys.argv[1:]
prompt = args[args.index("-z") + 1]
usage_path = Path(args[args.index("--usage-file") + 1])
home = Path(os.environ["HERMES_HOME"])
mode = os.environ.get("FAKE_HERMES_MODE", "ok")

if mode == "hang":
    time.sleep(60)
if mode == "crash":
    sys.exit(3)

session_id = f"s{len(list(home.glob('usage-*.json')))}"
conn = sqlite3.connect(home / "state.db")
conn.execute(
    "create table if not exists messages (id integer primary key, session_id text, role text,"
    " content text, tool_calls text, tool_call_id text, tool_name text, reasoning text, timestamp real)"
)
call = {
    "id": "c1",
    "type": "function",
    "function": {"name": "memory", "arguments": json.dumps({"content": prompt})},
}
rows = [
    ("user", prompt, None, None, None),
    ("assistant", None, json.dumps([call]), None, None),
    ("tool", json.dumps({"success": True}), None, "c1", "memory"),
    ("assistant", "ANSWER: 42", None, None, None),
]
for i, (role, content, calls, call_id, name) in enumerate(rows):
    conn.execute(
        "insert into messages (session_id, role, content, tool_calls, tool_call_id, tool_name, timestamp)"
        " values (?, ?, ?, ?, ?, ?, ?)",
        (session_id, role, content, calls, call_id, name, time.time() + i),
    )
conn.commit()
(home / "memories").mkdir(exist_ok=True)
with (home / "memories" / "MEMORY.md").open("a") as f:
    f.write(prompt + "\n")
usage = {
    "input_tokens": 100,
    "cache_read_tokens": 50,
    "output_tokens": 10,
    "session_id": session_id,
    "completed": mode != "turns",
    "failed": mode == "fail",
}
usage_path.write_text(json.dumps(usage))
print("ANSWER: 42")
