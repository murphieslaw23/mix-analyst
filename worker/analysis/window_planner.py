def plan_analysis_windows(
    duration_seconds: float,
    window_length_sec: float = 30.0,
    max_windows: int = 8,
) -> list[tuple[float, float]]:
    """
    Plan representative sampling windows across a long continuous mix.
    Bounds memory consumption by avoiding full-file decoding.
    """
    if duration_seconds <= window_length_sec:
        return [(0.0, duration_seconds)]

    # Skip first 2% and last 2% (intro / outro silence or crowd noise)
    start_margin = max(duration_seconds * 0.02, 5.0)
    end_margin = max(duration_seconds * 0.98 - window_length_sec, start_margin)

    if end_margin <= start_margin:
        return [(0.0, min(duration_seconds, window_length_sec))]

    step = (end_margin - start_margin) / max(max_windows - 1, 1)
    windows = []
    for i in range(max_windows):
        offset = start_margin + i * step
        windows.append((round(offset, 2), round(window_length_sec, 2)))

    return windows
