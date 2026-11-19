---
name: qlog-format
description: How to parse ACME .qlog access logs (field layout, units, which records count). Use whenever reading a .qlog file.
---
# ACME qlog format

One record per line, fields separated by `|`, no header:

| # | field | notes |
|---|-------|-------|
| 1 | timestamp | Unix epoch seconds |
| 2 | user id | e.g. `u17` |
| 3 | size | **hexadecimal, in KiB** (1 KiB = 1024 bytes). `7a` = 122 KiB = 124,928 bytes |
| 4 | flag | `-` normal transfer, `R` client retry of an earlier record, `C` served from cache |
| 5 | path | request path |

Counting rules for traffic / bytes questions:
- Count **only** records with flag `-`.
- `R` records duplicate an earlier transfer and must be excluded; `C` records transferred nothing.
- Report bytes = sum(int(size, 16) × 1024) over counted records.

Python sketch:
```python
total = 0
for line in open(path):
    ts, user, size, flag, p = line.rstrip("\n").split("|")
    if user == target and flag == "-":
        total += int(size, 16) * 1024
```
