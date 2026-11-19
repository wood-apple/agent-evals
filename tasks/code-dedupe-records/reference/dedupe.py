def dedupe(records):
    best = {}
    for r in records:
        key = r["email"].strip().lower()
        cur = best.get(key)
        if cur is None or r["updated_at"] >= cur["updated_at"]:
            best[key] = r
    return [dict(best[k], email=k) for k in sorted(best)]
