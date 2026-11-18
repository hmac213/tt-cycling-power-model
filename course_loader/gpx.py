"""Loads a course from a GPX track.

Pipeline:

    GPX points -> local metres -> smoothing splines -> exact derivatives
               -> dense resampling by distance ridden
"""

import pathlib
from xml.etree import ElementTree

import numpy as np
from scipy import interpolate

from course_loader import course as course_lib

# WGS84 ellipsoid: semi-major axis [m] and first eccentricity squared.
_WGS84_A = 6378137.0
_WGS84_E2 = 6.69437999014e-3

# Ratio of standard deviation to median absolute deviation, Gaussian noise.
_MAD_TO_SIGMA = 1.4826

# Elevation rounding steps [m] to test for, coarsest first.
_ELEVATION_QUANTA = (1.0, 0.5, 0.1)

# Below this noise level [m] the spline interpolates instead of smoothing.
_MIN_SIGMA = 1e-6

_MIN_POINTS = 4

Track = tuple[np.ndarray, np.ndarray, np.ndarray]


def _local_tag(element: ElementTree.Element) -> str:
    """Returns an XML element's tag without its namespace."""
    return element.tag.rsplit("}", 1)[-1]


def read_gpx_points(path: str | pathlib.Path) -> Track:
    """Reads the track points (or, failing that, route points) of a GPX file.

    Args:
        path: GPX file to read.

    Returns:
        Arrays (lat [deg], lon [deg], elevation [m]), one entry per point.

    Raises:
        ValueError: If the file has no points, or a point has no elevation.
    """
    root = ElementTree.parse(path).getroot()
    points = []
    for kind in ("trkpt", "rtept"):
        points = [el for el in root.iter() if _local_tag(el) == kind]
        if points:
            break
    if not points:
        raise ValueError(f"{path} has no track or route points")

    lat, lon, ele = [], [], []
    for point in points:
        elevation = None
        for child in point:
            if _local_tag(child) == "ele":
                elevation = child.text
        if elevation is None:
            raise ValueError(f"{path} has a point without <ele>")
        lat.append(float(point.get("lat")))
        lon.append(float(point.get("lon")))
        ele.append(float(elevation))
    return np.array(lat), np.array(lon), np.array(ele)


def write_gpx(
    path: str | pathlib.Path,
    lat: np.ndarray,
    lon: np.ndarray,
    ele: np.ndarray,
    name: str = "course",
) -> None:
    """Writes a single-track GPX file.

    Args:
        path: File to write.
        lat: Latitude of each point [deg].
        lon: Longitude of each point [deg].
        ele: Elevation of each point [m].
        name: Track name stored in the file.
    """
    rows = "\n".join(
        f'      <trkpt lat="{point_lat:.8f}" lon="{point_lon:.8f}">'
        f"<ele>{point_ele:.3f}</ele></trkpt>"
        for point_lat, point_lon, point_ele in zip(lat, lon, ele)
    )
    pathlib.Path(path).write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="tt-cycling-power-model" '
        'xmlns="http://www.topografix.com/GPX/1/1">\n'
        "  <trk>\n"
        f"    <name>{name}</name>\n"
        "    <trkseg>\n"
        f"{rows}\n"
        "    </trkseg>\n"
        "  </trk>\n"
        "</gpx>\n"
    )


def _mad_sigma(residuals: np.ndarray) -> float:
    """Returns a robust standard deviation of the residuals."""
    centred = residuals - np.median(residuals)
    return float(_MAD_TO_SIGMA * np.median(np.abs(centred)))


def estimate_elevation_noise(chord: np.ndarray, ele: np.ndarray) -> float:
    """Estimates the point-to-point noise level of an elevation profile.

    Each interior point is compared with the straight line through its two
    neighbours. A smooth profile barely departs from that line over one
    sample spacing, so what is left is noise. For independent noise of size
    sigma the residual has variance sigma^2 (1 + a^2 + b^2), where a and b
    are the interpolation weights. The median absolute deviation keeps a few
    sharp features from inflating the estimate.

    The result is floored at the rounding error of quantized data (elevations
    stored in whole metres or decimetres), which would otherwise look
    noise-free.

    Args:
        chord: Increasing horizontal distance of each point [m].
        ele: Elevation of each point [m].

    Returns:
        Estimated noise standard deviation [m].
    """
    weight_prev = (chord[2:] - chord[1:-1]) / (chord[2:] - chord[:-2])
    weight_next = 1.0 - weight_prev
    residuals = ele[1:-1] - weight_prev * ele[:-2] - weight_next * ele[2:]
    sigma = _mad_sigma(
        residuals / np.sqrt(1.0 + weight_prev**2 + weight_next**2)
    )
    for quantum in _ELEVATION_QUANTA:
        steps = ele / quantum
        if np.allclose(steps, np.round(steps), atol=1e-6):
            return max(sigma, quantum / np.sqrt(12.0))
    return sigma


def estimate_position_noise(east: np.ndarray, north: np.ndarray) -> float:
    """Estimates the point-to-point noise level of horizontal positions.

    Same idea as for elevation, but using each point's perpendicular distance
    from the chord joining its neighbours. Noise along the direction of
    travel cannot be told apart from uneven point spacing, so only the
    cross-track part is measured.

    Args:
        east: East coordinate of each point [m].
        north: North coordinate of each point [m].

    Returns:
        Estimated noise standard deviation per axis [m].
    """
    chord_east = east[2:] - east[:-2]
    chord_north = north[2:] - north[:-2]
    chord = np.hypot(chord_east, chord_north)
    valid = chord > 0
    offset_east = east[1:-1] - east[:-2]
    offset_north = north[1:-1] - north[:-2]

    cross = chord_east * offset_north - chord_north * offset_east
    along = chord_east * offset_east + chord_north * offset_north
    perpendicular = cross[valid] / chord[valid]
    weight_next = np.clip(along[valid] / chord[valid] ** 2, 0.0, 1.0)
    weight_prev = 1.0 - weight_next
    return _mad_sigma(
        perpendicular / np.sqrt(1.0 + weight_prev**2 + weight_next**2)
    )


def _metres_per_radian(lat_deg: float) -> tuple[float, float]:
    """Returns the local scale of the WGS84 ellipsoid.

    Args:
        lat_deg: Latitude [deg].

    Returns:
        Metres east per radian of longitude, and metres north per radian of
        latitude.
    """
    phi = np.radians(lat_deg)
    flattening = np.sqrt(1.0 - _WGS84_E2 * np.sin(phi) ** 2)
    east = _WGS84_A / flattening * np.cos(phi)
    north = _WGS84_A * (1.0 - _WGS84_E2) / flattening**3
    return float(east), float(north)


def _drop_close_points(
    east: np.ndarray, north: np.ndarray, min_spacing: float
) -> np.ndarray:
    """Returns indices of points at least `min_spacing` from the last kept."""
    keep = [0]
    for i in range(1, east.size):
        last = keep[-1]
        gap = np.hypot(east[i] - east[last], north[i] - north[last])
        if gap >= min_spacing:
            keep.append(i)
    return np.array(keep)


def _fit_spline(
    chord: np.ndarray, values: np.ndarray, sigma: float
) -> interpolate.UnivariateSpline:
    """Fits a cubic smoothing spline with RMS misfit equal to `sigma`.

    Args:
        chord: Increasing parameter of each sample [m].
        values: Sample values.
        sigma: Noise level of the samples; below `_MIN_SIGMA` the spline
            interpolates them exactly.

    Returns:
        The smoothest cubic spline consistent with that noise level.
    """
    if sigma <= _MIN_SIGMA:
        return interpolate.UnivariateSpline(chord, values, k=3, s=0)
    weights = np.full(chord.size, 1.0 / sigma)
    return interpolate.UnivariateSpline(
        chord, values, w=weights, k=3, s=chord.size
    )


def course_from_track(
    lat: np.ndarray,
    lon: np.ndarray,
    ele: np.ndarray,
    sigma_xy: float | None = None,
    sigma_ele: float | None = None,
    resolution: float = 1.0,
    min_spacing: float = 0.5,
    name: str = "course",
) -> course_lib.Course:
    """Builds a smooth course from raw track points.

    Args:
        lat: Latitude of each point [deg].
        lon: Longitude of each point [deg].
        ele: Elevation of each point [m].
        sigma_xy: Horizontal position noise of the track [m]. None estimates
            it from the data; 0 disables smoothing, so the curve passes
            through every point.
        sigma_ele: Elevation noise of the track [m], with the same
            conventions as `sigma_xy`.
        resolution: Spacing of the output samples along the road [m].
        min_spacing: Points closer than this to the previous kept point are
            dropped [m].
        name: Label for the course.

    Returns:
        The course, sampled every `resolution` metres of distance ridden.

    Raises:
        ValueError: If fewer than four distinct points remain.
    """
    lat = np.asarray(lat, float)
    lon = np.asarray(lon, float)
    ele = np.asarray(ele, float)

    # Project to local east/north metres about the centre of the track.
    lat0 = lat.mean()
    lon0 = lon.mean()
    east_scale, north_scale = _metres_per_radian(lat0)
    east = np.radians(lon - lon0) * east_scale
    north = np.radians(lat - lat0) * north_scale

    # Drop stationary points, then parameterize by chord length.
    keep = _drop_close_points(east, north, min_spacing)
    if keep.size < _MIN_POINTS:
        raise ValueError(f"need at least {_MIN_POINTS} distinct track points")
    east, north, ele = east[keep], north[keep], ele[keep]
    hops = np.hypot(np.diff(east), np.diff(north))
    chord = np.concatenate([[0.0], np.cumsum(hops)])

    if sigma_xy is None:
        sigma_xy = estimate_position_noise(east, north)
    if sigma_ele is None:
        sigma_ele = estimate_elevation_noise(chord, ele)
    east_fit = _fit_spline(chord, east, sigma_xy)
    north_fit = _fit_spline(chord, north, sigma_xy)
    ele_fit = _fit_spline(chord, ele, sigma_ele)

    # Evaluate the fit and its derivatives on a grid finer than the output.
    num_fine = int(np.ceil(chord[-1] / (0.5 * resolution))) + 1
    fine = np.linspace(0.0, chord[-1], num_fine)
    d_east = east_fit(fine, 1)
    d_north = north_fit(fine, 1)
    d_ele = ele_fit(fine, 1)
    dd_east = east_fit(fine, 2)
    dd_north = north_fit(fine, 2)
    horizontal_rate = np.hypot(d_east, d_north)
    road_rate = np.hypot(horizontal_rate, d_ele)

    theta = np.arctan2(d_ele, horizontal_rate)
    heading = np.unwrap(np.arctan2(d_east, d_north))
    curvature = (dd_east * d_north - d_east * dd_north) / horizontal_rate**3

    # Re-parameterize by distance ridden: 3-D arc length of the smooth curve.
    increments = 0.5 * (road_rate[1:] + road_rate[:-1]) * np.diff(fine)
    ridden = np.concatenate([[0.0], np.cumsum(increments)])
    num_samples = int(np.ceil(ridden[-1] / resolution)) + 1
    distance = np.linspace(0.0, ridden[-1], num_samples)

    def resample(values: np.ndarray) -> np.ndarray:
        return np.interp(distance, ridden, values)

    return course_lib.Course(
        distance=distance,
        elevation=resample(ele_fit(fine)),
        theta=resample(theta),
        heading=resample(heading),
        curvature=resample(curvature),
        lat=lat0 + np.degrees(resample(north_fit(fine)) / north_scale),
        lon=lon0 + np.degrees(resample(east_fit(fine)) / east_scale),
        headwind=np.zeros_like(distance),
        name=name,
        sigma_xy=float(sigma_xy),
        sigma_ele=float(sigma_ele),
    )


def load_gpx(
    path: str | pathlib.Path,
    sigma_xy: float | None = None,
    sigma_ele: float | None = None,
    resolution: float = 1.0,
    wind_speed: float = 0.0,
    wind_from_deg: float = 0.0,
    name: str | None = None,
) -> course_lib.Course:
    """Loads a GPX file as a smooth course, optionally with a uniform wind.

    Args:
        path: GPX file to read.
        sigma_xy: Horizontal position noise of the track [m]. None estimates
            it from the data; 0 disables smoothing.
        sigma_ele: Elevation noise of the track [m], with the same
            conventions as `sigma_xy`.
        resolution: Spacing of the output samples along the road [m].
        wind_speed: Speed of a uniform wind [m/s].
        wind_from_deg: Compass bearing the wind blows from [deg]; 0 is a wind
            from the north.
        name: Label for the course. Defaults to the file name.

    Returns:
        The loaded course.
    """
    lat, lon, ele = read_gpx_points(path)
    course = course_from_track(
        lat,
        lon,
        ele,
        sigma_xy=sigma_xy,
        sigma_ele=sigma_ele,
        resolution=resolution,
        name=name or pathlib.Path(path).stem,
    )
    if wind_speed:
        course = course.with_wind(wind_speed, wind_from_deg)
    return course
