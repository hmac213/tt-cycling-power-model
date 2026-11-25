"""Generates the race courses: two reconstructed championship courses and a
loop of our own design.

    python -m courses.make_race_gpx

Writes, into this folder:

* tokyo_2021_men.gpx / tokyo_2021_women.gpx: the 2021 Olympic time trial at
  Fuji International Speedway. Two laps (44.2 km) for the men, one lap
  (22.1 km) for the women.
* flanders_2021_men.gpx / flanders_2021_women.gpx: the 2021 UCI World
  Championship time trial from Knokke-Heist to Bruges, 43.3 km for the men
  and 30.3 km for the women.
* custom_loop.gpx: our own 12 km course with six sharp corners, a 7% climb,
  and the finish line on top of the start line.

The two championship courses are RECONSTRUCTIONS, not surveyed tracks. They
match the published length, total climbing, order and size of the climbs, and
the start and finish, but the road layout is schematic: a polygon with
rounded corners of realistic radii. To use the real roads, drop the official
GPX file into this folder and load it instead; nothing else changes.

Published facts used:

Tokyo (one 22.1 km lap, about 423 m climbing): starts on the circuit's
start-finish straight (about 1.5 km flat), descends for about 4 km, climbs
about 5 km at about 4.5% to the high point south of the circuit, rolls along
route 151 past two golf courses, descends about 5 km back to the circuit,
climbs about 2 km at 4.5% back to the start-finish straight, then rolls to
the line.

Flanders (point to point, flat): starts on the seafront in Knokke-Heist,
winds inland, makes a 180-degree turn, runs straight about 5 km into Damme,
follows the canal into Bruges, and finishes at 't Zand after a few city-centre
corners with a gradual rise to the line. The women's course skips part of
the inland section.
"""

import pathlib

import numpy as np
from scipy import optimize

from course_loader import gpx

_OUTPUT_DIR = pathlib.Path(__file__).resolve().parent
_POINT_SPACING = 5.0  # [m]

# Local metres per degree at about 35 N and 51 N.
_METRES_PER_DEG = {
    "tokyo": (110_950.0, 91_000.0),
    "flanders": (111_250.0, 69_700.0),
    "custom": (110_922.0, 92_385.0),
}
_ORIGINS = {
    "tokyo": (35.3717, 138.9271),     # Fuji International Speedway
    "flanders": (51.3500, 3.2860),    # Knokke-Heist seafront
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


# --------------------------------------------------------------------- Tokyo
_TOKYO_VERTICES = [  # km, schematic lap layout around and south of the circuit
    (0.0, 0.0), (1.5, 0.0), (0.7, -0.5), (-1.4, -2.6), (-0.6, -6.3),
    (2.3, -8.4), (4.4, -6.1), (3.6, -2.7), (2.3, -1.3), (2.7, 0.7),
    (0.6, 1.0),
]
_TOKYO_RADII = [25, 14, 30, 25, 60, 40, 35, 20, 15, 20, 25]  # m
_TOKYO_GRADES = (  # (km breakpoints, grade %) for one 22.1 km lap
    [0, 1.5, 4.5, 9.5, 11.5, 13.5, 18.5, 20.5, 21.3, 22.1],
    [0.0, -3.0, 4.8, 1.5, -1.5, -4.9, 4.5, 1.0, -0.375],
)


def tokyo_lap():
    xy = fit_length(_TOKYO_VERTICES, _TOKYO_RADII, True, 22_100.0)
    s = along(xy)
    elevation = grade_profile(s, *_TOKYO_GRADES)
    # Rollers bring the climbing up to the published 423 m per lap.
    elevation += 11.0 * np.sin(2 * np.pi * 8 * s / s[-1])
    elevation += 560.0 - elevation[0]  # circuit altitude, roughly
    return xy, elevation


def write_tokyo():
    xy, elevation = tokyo_lap()
    write("tokyo_2021_women", "tokyo", xy, elevation)
    write("tokyo_2021_men", "tokyo", np.vstack([xy, xy[1:]]),
          np.concatenate([elevation, elevation[1:]]))


# ------------------------------------------------------------------ Flanders
_FLANDERS_MEN = [  # km from the Knokke-Heist seafront start
    (0.0, 0.0), (-3.0, -0.8), (-3.5, -4.0), (1.5, -6.0), (4.0, -9.0),
    (5.0, -13.0), (1.0, -10.5), (-2.5, -11.5), (-4.5, -15.0),
    (-4.0, -15.8), (-5.0, -16.2), (-5.3, -16.0),
]
_FLANDERS_MEN_RADII = [0, 30, 20, 25, 20, 10, 20, 20, 25, 10, 10, 0]
_FLANDERS_WOMEN = [
    (0.0, 0.0), (-3.0, -0.8), (-3.5, -4.0), (0.5, -6.5), (2.6, -9.6),
    (-2.5, -11.5), (-4.5, -15.0), (-4.0, -15.8), (-5.0, -16.2),
    (-5.3, -16.0),
]
_FLANDERS_WOMEN_RADII = [0, 30, 20, 25, 12, 20, 25, 10, 10, 0]


def flanders(vertices, radii, length):
    xy = fit_length(vertices, radii, False, length)
    s = along(xy)
    frac = s / s[-1]
    elevation = 4.0 + 0.0 * s
    for centre in (0.15, 0.4, 0.62, 0.85):  # bridges over canals
        elevation += 4.0 * np.exp(-0.5 * ((s - centre * s[-1]) / 60.0) ** 2)
    elevation += 8.0 * np.clip((frac - 0.88) / 0.12, 0, 1)  # rise to finish
    return xy, elevation


def write_flanders():
    write("flanders_2021_men", "flanders",
          *flanders(_FLANDERS_MEN, _FLANDERS_MEN_RADII, 43_300.0))
    write("flanders_2021_women", "flanders",
          *flanders(_FLANDERS_WOMEN, _FLANDERS_WOMEN_RADII, 30_300.0))


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
    write_tokyo()
    write_flanders()
    write_custom()


if __name__ == "__main__":
    main()
