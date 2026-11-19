def find_first(items, target):
    """Return the index of the first occurrence of target in sorted items, or -1."""
    lo, hi = 0, len(items) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if items[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    if items and items[lo] == target:
        return lo
    return -1
