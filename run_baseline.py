"""Runs the pacing model for one rider on one GPX course.

Compares the optimal pacing plan with the best constant-power ride, and
writes a plot, the pacing plan, and the course profile to an output folder.

    python run_baseline.py                      # rolling.gpx, TT specialist
    python run_baseline.py courses/hill.gpx --profile climber
    python run_baseline.py ride.gpx --wind-speed 4 --wind-from 270
"""

import argparse
import pathlib
import time

import matplotlib
import numpy as np

from course_loader import course as course_lib
from course_loader import gpx
from physics_model import params as physics_params
from power_model import params as rider_params
from profiles import rider as rider_profiles
from solver import optimize
from solver import simulate

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # pylint: disable=wrong-import-position

_DEFAULT_GPX = pathlib.Path(__file__).resolve().parent / "courses/rolling.gpx"

# Corners with a limit above this speed [m/s] are not worth reporting.
_FAST_CORNER_SPEED = 30.0

_OPTIMAL_COLOR = "#2a78d6"
_BASELINE_COLOR = "#8a8984"
_INK_COLOR = "#0b0b0b"
_MUTED_COLOR = "#52514e"
_GRID_COLOR = "#e6e5e0"
_AXIS_COLOR = "#c9c8c2"
_FILL_COLOR = "#d9d8d2"


def _format_time(seconds: float) -> str:
    """Formats a duration as m:ss.s."""
    minutes, rest = divmod(seconds, 60.0)
    return f"{int(minutes)}:{rest:04.1f}"


def _parse_args() -> argparse.Namespace:
    """Parses the command line."""
    physics = physics_params.PhysicsParams()
    config = simulate.SimConfig()
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "gpx", nargs="?", default=str(_DEFAULT_GPX), help="course GPX file"
    )
    parser.add_argument(
        "--wind-speed", type=float, default=0.0, help="uniform wind [m/s]"
    )
    parser.add_argument(
        "--wind-from", type=float, default=0.0,
        help="compass bearing the wind blows from [deg]",
    )
    parser.add_argument(
        "--sigma-xy", type=float, default=None,
        help="GPS position noise [m]; default estimates it, 0 = no smoothing",
    )
    parser.add_argument(
        "--sigma-ele", type=float, default=None,
        help="GPS elevation noise [m]; default estimates it, 0 = no smoothing",
    )
    parser.add_argument(
        "--profile", default="tt_specialist",
        help=(
            "rider profile: a name from profiles/ ("
            + ", ".join(rider_profiles.available())
            + ") or the path of a profile JSON file"
        ),
    )
    parser.add_argument(
        "--step", type=float, default=config.step_length,
        help="length of one grid step [m]",
    )
    parser.add_argument("--mu-corner", type=float, default=physics.mu_corner)
    parser.add_argument(
        "--brake-decel", type=float, default=physics.brake_decel
    )
    parser.add_argument(
        "--no-polish", action="store_true",
        help="stop after the dynamic program (skip collocation)",
    )
    parser.add_argument(
        "--out", default="outputs", help="directory for the results"
    )
    parser.add_argument("--no-plot", action="store_true")
    return parser.parse_args()


def _describe_course(course: course_lib.Course, envelope: np.ndarray) -> None:
    """Prints a one-paragraph summary of the course."""
    grade = 100.0 * np.tan(course.theta)
    print(
        f"Course '{course.name}': {course.length / 1000:.2f} km, "
        f"{course.total_climb:.0f} m climbing, "
        f"grade {grade.min():+.1f}% to {grade.max():+.1f}%"
    )
    print(
        f"  smoothing: position noise {course.sigma_xy:.2f} m, "
        f"elevation noise {course.sigma_ele:.2f} m"
    )
    if envelope.min() < _FAST_CORNER_SPEED:
        print(f"  slowest corner: {3.6 * envelope.min():.1f} km/h")
    else:
        print("  no corners tight enough to limit speed")


def _describe_profile(profile: rider_profiles.RiderProfile) -> None:
    """Prints a one-paragraph summary of the rider."""
    print(
        f"Rider '{profile.name}': {profile.rider_mass:.0f} kg + "
        f"{profile.bike_mass:.0f} kg bike, CdA {profile.cda:.2f} m^2, "
        f"CP {profile.cp:.0f} W ({profile.cp_per_kg:.2f} W/kg), "
        f"W' {profile.w_prime / 1000:.0f} kJ, P_max {profile.p_max:.0f} W"
    )


def _describe_ride(label: str, ride: simulate.RideResult) -> None:
    """Prints a one-line summary of a ride."""
    mean_power = np.sum(ride.power * np.diff(ride.time)) / ride.total_time
    mean_speed = 3.6 * ride.distance[-1] / ride.total_time
    print(
        f"  {label:<15} {_format_time(ride.total_time)} "
        f"({ride.total_time:8.2f} s)  mean power {mean_power:5.1f} W  "
        f"avg speed {mean_speed:5.2f} km/h  "
        f"braked {ride.brake_energy.sum() / 1000:5.2f} kJ  "
        f"final B {ride.reserve[-1] / 1000:5.2f} kJ"
    )


def _write_tables(
    course: course_lib.Course,
    envelope: np.ndarray,
    ride: simulate.RideResult,
    stem: str,
    out_dir: pathlib.Path,
) -> None:
    """Writes the pacing plan and the course profile as CSV files."""
    pacing = np.column_stack([
        ride.distance[:-1],
        ride.distance[1:],
        ride.power,
        ride.speed[1:],
        ride.time[1:],
        ride.reserve[1:],
        ride.brake_energy,
    ])
    np.savetxt(
        out_dir / f"{stem}_pacing.csv",
        pacing,
        delimiter=",",
        fmt="%.3f",
        comments="",
        header=(
            "start_m,end_m,power_w,end_speed_mps,end_time_s,"
            "end_reserve_j,brake_energy_j"
        ),
    )
    profile = np.column_stack([
        course.distance,
        course.lat,
        course.lon,
        course.elevation,
        np.tan(course.theta),
        np.degrees(course.heading) % 360,
        course.curvature,
        course.headwind,
        envelope,
    ])
    np.savetxt(
        out_dir / f"{course.name}_course.csv",
        profile,
        delimiter=",",
        fmt=[
            "%.1f", "%.7f", "%.7f", "%.2f", "%.5f", "%.2f", "%.6f", "%.3f",
            "%.2f",
        ],
        comments="",
        header=(
            "distance_m,lat,lon,elevation_m,grade,heading_deg,"
            "curvature_per_m,headwind_mps,speed_envelope_mps"
        ),
    )


def _style_axes(axes: plt.Axes, title: str) -> None:
    """Applies the shared look to one panel."""
    axes.set_title(title, loc="left", fontsize=10, color=_INK_COLOR)
    axes.grid(True, color=_GRID_COLOR, linewidth=0.6)
    axes.tick_params(colors=_MUTED_COLOR, labelsize=9)
    for side in ("top", "right"):
        axes.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axes.spines[side].set_color(_AXIS_COLOR)


def _add_legend(axes: plt.Axes) -> None:
    """Places a frameless legend above the top-right corner of a panel."""
    axes.legend(
        frameon=False,
        fontsize=9,
        loc="lower right",
        bbox_to_anchor=(1.0, 1.0),
        ncols=3,
        borderaxespad=0.2,
    )


def _plot(
    course: course_lib.Course,
    envelope: np.ndarray,
    optimal: simulate.RideResult,
    constant: simulate.RideResult,
    rider: rider_params.RiderParams,
    title: str,
    path: pathlib.Path,
) -> None:
    """Draws the course and both rides as stacked panels over distance."""
    course_km = course.distance / 1000.0
    ride_km = optimal.distance / 1000.0
    fig, panels = plt.subplots(
        5, 1, figsize=(9, 11), sharex=True, constrained_layout=True
    )
    elevation_axes, wind_axes, power_axes, speed_axes, reserve_axes = panels

    elevation_axes.fill_between(
        course_km, course.elevation, color=_FILL_COLOR, linewidth=0
    )
    _style_axes(elevation_axes, "Elevation (m)")

    wind_axes.plot(
        course_km, course.headwind, color=_MUTED_COLOR, linewidth=1.5
    )
    wind_axes.axhline(0, color=_AXIS_COLOR, linewidth=0.8)
    _style_axes(wind_axes, "Headwind (m/s)")

    power_axes.stairs(
        constant.power, ride_km, baseline=None, color=_BASELINE_COLOR,
        linewidth=1.5, label="Constant power",
    )
    power_axes.stairs(
        optimal.power, ride_km, baseline=None, color=_OPTIMAL_COLOR,
        linewidth=2, label="Optimal",
    )
    power_axes.axhline(
        rider.cp, color=_MUTED_COLOR, linewidth=0.8, linestyle=":"
    )
    power_axes.annotate(
        "CP", (ride_km[-1], rider.cp), xytext=(6, 0),
        textcoords="offset points", va="center", fontsize=9,
        color=_MUTED_COLOR, annotation_clip=False,
    )
    _style_axes(power_axes, "Power (W)")
    _add_legend(power_axes)

    speed_axes.plot(
        course_km, 3.6 * envelope, color=_MUTED_COLOR, linewidth=0.8,
        linestyle=":", label="Corner limit",
    )
    speed_axes.plot(
        ride_km, 3.6 * constant.speed, color=_BASELINE_COLOR, linewidth=1.5,
        label="Constant power",
    )
    speed_axes.plot(
        ride_km, 3.6 * optimal.speed, color=_OPTIMAL_COLOR, linewidth=2,
        label="Optimal",
    )
    top_speed = max(constant.speed.max(), optimal.speed.max())
    speed_axes.set_ylim(0, 3.6 * 1.1 * top_speed)
    _style_axes(speed_axes, "Speed (km/h)")
    _add_legend(speed_axes)

    reserve_axes.plot(
        ride_km, constant.reserve / 1000, color=_BASELINE_COLOR,
        linewidth=1.5,
    )
    reserve_axes.plot(
        ride_km, optimal.reserve / 1000, color=_OPTIMAL_COLOR, linewidth=2
    )
    _style_axes(reserve_axes, "Anaerobic reserve B (kJ)")
    reserve_axes.set_xlabel("Distance (km)", color=_MUTED_COLOR, fontsize=9)

    saved = constant.total_time - optimal.total_time
    fig.suptitle(
        f"{title}: optimal {_format_time(optimal.total_time)} vs "
        f"constant power {_format_time(constant.total_time)} "
        f"({saved:.1f} s saved)",
        x=0.01, ha="left", fontsize=12, color=_INK_COLOR,
    )
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    args = _parse_args()
    profile = rider_profiles.load(args.profile)
    physics = profile.physics_params(
        physics_params.PhysicsParams(
            mu_corner=args.mu_corner, brake_decel=args.brake_decel
        )
    )
    rider = profile.rider_params()
    config = simulate.SimConfig(step_length=args.step)
    course = gpx.load_gpx(
        args.gpx,
        sigma_xy=args.sigma_xy,
        sigma_ele=args.sigma_ele,
        wind_speed=args.wind_speed,
        wind_from_deg=args.wind_from,
    )
    envelope = simulate.course_speed_envelope(course, physics, config)
    _describe_course(course, envelope)
    _describe_profile(profile)

    constant = optimize.constant_power_ride(course, physics, rider, config)
    started = time.perf_counter()
    result = optimize.optimize_pacing(
        course, physics, rider, config, polish=not args.no_polish
    )
    elapsed = time.perf_counter() - started
    step = course.length / result.ride.power.size
    print(
        f"Solver: {result.ride.power.size} steps of {step:.1f} m, "
        f"{elapsed:.1f} s; stage 2: {result.message}"
    )
    _describe_ride("constant power", constant)
    _describe_ride("optimal (DP)", result.dp_ride)
    if result.polished:
        _describe_ride("optimal", result.ride)
    saved = constant.total_time - result.ride.total_time
    print(f"  time saved: {saved:.2f} s")

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{course.name}_{pathlib.Path(args.profile).stem}"
    _write_tables(course, envelope, result.ride, stem, out_dir)
    if not args.no_plot:
        _plot(
            course, envelope, result.ride, constant, rider,
            f"{course.name}, {profile.name}", out_dir / f"{stem}_pacing.png",
        )
    print(f"Wrote results to {out_dir}/")


if __name__ == "__main__":
    main()
