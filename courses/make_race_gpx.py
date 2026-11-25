"""Generates custom_loop.gpx, the course of our own design.

    python -m courses.make_race_gpx

A 12 km loop with seven sharp corners (80 degrees or more, radius 12-20 m),
a 1.5 km climb that reaches 7%, and the finish line on top of the start
line: what the problem statement asks of a course of our own design.

The 2021 Tokyo and Flanders courses are real routes downloaded from
RideWithGPS, not generated here; see courses/README.md.
"""

import pathlib

import numpy as np
from scipy import optimize

from course_loader import gpx

_OUTPUT_DIR = pathlib.Path(__file__).resolve().parent
_POINT_SPACING = 5.0  # [m]

# Local metres per degree at the course origin.
_METRES_PER_DEG = {
    "custom": (110_922.0, 92_385.0),
}
_ORIGINS = {
    "custom": (34.0500, -118.4500),   # arbitrary
}


def rounded_path(
    vertices: np.ndarray, radii: np.ndarray, closed: bool, spacing: float
) -> tuple[np.ndarray, float]:
    """Lays out straights joined by circular arcs through polygon vertices.

    Args:
        vertices: Polygon vertices [m], shape (n, 2), as (east, north).
        radii: Corner radius at each vertex [m]. For an open path the first
            and last entries are ignored.
        closed: Whether the path returns to its start. A closed path starts
            and ends halfway along the edge from vertex 0 to vertex 1.
        spacing: Distance between output points [m].

    Returns:
        Points along the path [m], shape (N, 2), and its length [m].

    Raises:
        ValueError: If two corners overlap on one edge.
    """
    n = len(vertices)
    if closed:
        corners = range(n)
    else:
        corners = range(1, n - 1)

    def direction(a, b):
        d = vertices[b % n] - vertices[a % n]
        return d / np.linalg.norm(d)

    # For each corner: tangent points and arc.
    pieces = {}
    for i in corners:
        d_in = direction(i - 1, i)
        d_out = direction(i, i + 1)
        turn = np.arctan2(
            d_in[0] * d_out[1] - d_in[1] * d_out[0], d_in @ d_out
        )
        tangent = radii[i] * np.tan(abs(turn) / 2)
        enter = vertices[i] - tangent * d_in
        leave = vertices[i] + tangent * d_out
        normal = np.array([-d_in[1], d_in[0]]) * np.sign(turn)
        centre = enter + radii[i] * normal
        pieces[i] = (enter, leave, centre, turn, tangent)

    # Walk the path as a list of segments: ("line", a, b) or ("arc", ...).
    segments = []
    if closed:
        start = 0.5 * (vertices[0] + vertices[1])
        order = list(range(1, n)) + [0]
        position = start
        for i in order:
            enter, leave, centre, turn, _ = pieces[i]
            segments.append(("line", position, enter))
            segments.append(("arc", enter, centre, turn))
            position = leave
        segments.append(("line", position, start))
    else:
        position = vertices[0]
        for i in range(1, n - 1):
            enter, leave, centre, turn, _ = pieces[i]
            segments.append(("line", position, enter))
            segments.append(("arc", enter, centre, turn))
            position = leave
        segments.append(("line", position, vertices[-1]))

    # Neighbouring corners must not overlap on the edge between them.
    for i in range(n if closed else n - 1):
        edge = np.linalg.norm(vertices[(i + 1) % n] - vertices[i])
        used = sum(pieces[j][4] for j in (i, (i + 1) % n) if j in pieces)
        if used > edge:
            raise ValueError(f"corners {i} and {(i + 1) % n} overlap")

    # Sample densely.
    points = []
    total = 0.0
    for seg in segments:
        if seg[0] == "line":
            a, b = seg[1], seg[2]
            length = np.linalg.norm(b - a)
            m = max(1, int(np.ceil(length / 1.0)))
            t = np.linspace(0, 1, m, endpoint=False)
            points.append(a + t[:, None] * (b - a))
        else:
            enter, centre, turn = seg[1], seg[2], seg[3]
            radius = np.linalg.norm(enter - centre)
            length = radius * abs(turn)
            m = max(2, int(np.ceil(length / 1.0)))
            start_angle = np.arctan2(*(enter - centre)[::-1])
            angles = start_angle + np.linspace(0, turn, m, endpoint=False)
            points.append(
                centre + radius * np.column_stack([np.cos(angles), np.sin(angles)])
            )
        total += length
    end = segments[-1][2]
    dense = np.vstack(points + [end[None, :]])
    chord = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(dense, axis=0), axis=1))])
    s = np.arange(0.0, chord[-1], spacing)
    s = np.append(s, chord[-1])
    out = np.column_stack([np.interp(s, chord, dense[:, 0]), np.interp(s, chord, dense[:, 1])])
    return out, float(chord[-1])


def fit_length(vertices_km, radii, closed, target):
    """Scales the polygon so the rounded path has the target length [m]."""
    vertices_km = np.asarray(vertices_km, float)
    radii = np.asarray(radii, float)

    def excess(scale):
        return rounded_path(vertices_km * scale, radii, closed, 50.0)[1] - target

    scale = optimize.brentq(excess, 200.0, 5000.0, xtol=1e-3)
    return rounded_path(vertices_km * scale, radii, closed, _POINT_SPACING)[0]


def grade_profile(distance, breakpoints_km, grades_pct):
    """Integrates a piecewise-constant grade into an elevation profile."""
    edges = np.asarray(breakpoints_km) * 1000.0
    grade = np.zeros_like(distance)
    for (a, b), g in zip(zip(edges[:-1], edges[1:]), grades_pct):
        grade[(distance >= a) & (distance < b)] = g / 100.0
    step = np.diff(distance, prepend=distance[0])
    return np.cumsum(grade * step)


def write(name, region, xy, elevation):
    lat0, lon0 = _ORIGINS[region]
    per_lat, per_lon = _METRES_PER_DEG[region]
    lat = lat0 + xy[:, 1] / per_lat
    lon = lon0 + xy[:, 0] / per_lon
    gpx.write_gpx(_OUTPUT_DIR / f"{name}.gpx", lat, lon, elevation, name=name)


def along(xy):
    return np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(xy, axis=0), axis=1))])


# -------------------------------------------------------------- Custom loop
_CUSTOM_VERTICES = [
    (0.0, 0.0), (2.2, 0.0), (2.2, 1.4), (3.4, 1.4), (3.4, 2.8),
    (1.6, 2.2), (1.2, 3.0), (-0.8, 3.0), (-0.8, 0.0),
]
# Turns at the vertices [deg]: 0, 90, -90, 90, 108, -82, 63, 90, 90. That is
# seven sharp corners (80 degrees or more, radius 12-20 m) and one faster
# 63-degree bend.
_CUSTOM_RADII = [25, 15, 18, 15, 12, 20, 40, 15, 18]
_CUSTOM_GRADES = (
    [0, 2.0, 3.5, 4.4, 5.6, 7.0, 9.0, 12.0],
    [0.0, 3.0, 7.0, 2.0, -6.0, -2.4, 0.0],
)


def write_custom():
    xy = fit_length(_CUSTOM_VERTICES, _CUSTOM_RADII, True, 12_000.0)
    s = along(xy)
    elevation = grade_profile(s, *_CUSTOM_GRADES)
    elevation += 50.0 - elevation[0]
    write("custom_loop", "custom", xy, elevation)


def main():
    write_custom()


if __name__ == "__main__":
    main()
