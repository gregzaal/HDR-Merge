def chunks(l, n):
    if n < 1:
        n = 1
    return [l[i : i + n] for i in range(0, len(l), n)]