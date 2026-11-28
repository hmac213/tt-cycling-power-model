"""Runs every experiment the problem statement asks for.

    python -m analysis.run_analysis all            # everything
    python -m analysis.run_analysis courses        # one part at a time
    python -m analysis.run_analysis wind
    python -m analysis.run_analysis deviation
    python -m analysis.run_analysis fatigue

Parts:

* courses: every rider profile on the Tokyo and Flanders courses (men's or
  women's version to match the rider) and on our custom loop, optimal vs.
  constant power, with the full stamina model and with the classic
  Critical Power model (no loss of durability) for comparison.
* wind: wind from 8 directions at 2, 4 and 6 m/s on a point-to-point course
  (Flanders) and a loop (Tokyo), re-optimized for each; plus a plan made for
  the forecast wind ridden in slightly different wind.
* deviation: Monte Carlo of a rider missing their power targets by random
  and systematic errors, with the range of split times at key points.
* fatigue: sensitivity of the Tokyo result to the fatigue time tau_F.

Results go to outputs/analysis/ as JSON (summaries) and NPZ (full rides).
The collocation polish runs if CasADi is installed; pass --no-polish to use
the dynamic program alone.
"""

import argparse
import dataclasses
import importlib.util
import json
import multiprocessing
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs" / "analysis"

COURSES = {
    "tokyo": {"men": "tokyo_2021_men", "women": "tokyo_2021_women"},
    "flanders": {"men": "flanders_2021_men", "women": "flanders_2021_women"},
    "custom": {"men": "custom_loop", "women": "custom_loop"},
}
PROFILES = {
    "tt_specialist": "men",
    "climber": "men",
    "tt_specialist_women": "women",
    "climber_women": "women",
}
# Rider overrides that turn the loss of durability off, which leaves the
# classic Critical Power model. Used in the "classic" comparison runs.
CLASSIC = dict(fatigue_time=1e9, work_capacity=1e15)

POLISH = True


def _setup(polish):
    """Lets the solver import without CasADi when the polish is off."""
    global POLISH
    POLISH = polish
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    if (not polish and "casadi" not in sys.modules
            and importlib.util.find_spec("casadi") is None):
        stub = types.ModuleType("casadi")
        stub.SX = stub.MX = stub.DM = stub.Function = object
        sys.modules["casadi"] = stub


# Real courses with map-derived elevation: see courses/README.md.
MAP_ELEVATION_SIGMA = 1.0  # [m]


def _load(course_name, wind_speed=0.0, wind_from=0.0):
    from course_loader import gpx
    real = course_name.startswith(("tokyo_2021", "flanders_2021"))
    return gpx.load_gpx(
        ROOT / "courses" / f"{course_name}.gpx",
        sigma_ele=MAP_ELEVATION_SIGMA if real else None,
        wind_speed=wind_speed, wind_from_deg=wind_from,
    )


# Air density on race day [kg/m^3]. Tokyo: Fuji Speedway, about 500-700 m
# up on a hot day. Flanders: sea level. Custom loop: taken as sea level.
AIR_DENSITY = {"tokyo_2021": 1.15, "flanders_2021": 1.20, "custom": 1.20}


def _physics(profile, course_name):
    """Builds a rider's physics parameters at the venue of a course."""
    from physics_model import params as physics_params
    rho = next(value for prefix, value in AIR_DENSITY.items()
               if course_name.startswith(prefix))
    return profile.physics_params(physics_params.PhysicsParams(rho=rho))


def _solve(job):
    """Solves one (course, profile, wind, fatigue) case. Runs in a worker."""
    _setup(job["polish"])
    import numpy as np
    from profiles import rider as rider_profiles
    from solver import optimize

    course = _load(job["course"], job.get("wind_speed", 0.0), job.get("wind_from", 0.0))
    profile = rider_profiles.load(job["profile"])
    physics = _physics(profile, job["course"])
    rider = profile.rider_params()
    if job.get("fatigue"):
        rider = dataclasses.replace(rider, **job["fatigue"])
    constant = optimize.constant_power_ride(course, physics, rider)
    result = optimize.optimize_pacing(course, physics, rider, polish=job["polish"])
    ride = result.ride
    summary = dict(
        job,
        length_km=course.length / 1000,
        climb_m=course.total_climb,
        constant_time=constant.total_time,
        constant_power=float(constant.power.mean()),
        optimal_time=ride.total_time,
        saved=constant.total_time - ride.total_time,
        optimal_avg_power=float(np.sum(ride.power * np.diff(ride.time)) / ride.total_time),
        brake_constant_kj=float(constant.brake_energy.sum() / 1000),
        brake_optimal_kj=float(ride.brake_energy.sum() / 1000),
        polished=result.polished,
    )
    arrays = dict(
        distance=ride.distance, power=ride.power, speed=ride.speed,
        time=ride.time, reserve=ride.reserve, cp=ride.critical_power,
        c_power=constant.power, c_speed=constant.speed,
        c_time=constant.time, c_reserve=constant.reserve,
    )
    return summary, arrays


def _run_jobs(jobs, name, workers):
    import numpy as np
    for job in jobs:
        job["polish"] = POLISH
    with multiprocessing.Pool(workers) as pool:
        results = []
        for summary, arrays in pool.imap(_solve, jobs):
            results.append(summary)
            key = summary["tag"]
            np.savez_compressed(OUT / f"{name}__{key}.npz", **arrays)
            print(f"  {key:45s} {summary['constant_time']:8.1f} -> "
                  f"{summary['optimal_time']:8.1f}  ({summary['saved']:.1f} s)",
                  flush=True)
            (OUT / f"{name}.json").write_text(json.dumps(results, indent=1))
    return results


def part_courses(workers):
    print("courses")
    jobs = []
    for course, versions in COURSES.items():
        for profile, gender in PROFILES.items():
            for fatigue in (None, CLASSIC):
                if fatigue and course == "custom":
                    continue  # too short for durability to matter
                tag = f"{course}__{profile}" + ("__classic" if fatigue else "")
                jobs.append(dict(tag=tag, course=versions[gender],
                                 profile=profile, fatigue=fatigue))
    _run_jobs(jobs, "courses", workers)


def part_wind(workers):
    print("wind")
    jobs = []
    cases = (("flanders", "flanders_2021_men", "tt_specialist"),
             ("tokyo", "tokyo_2021_women", "tt_specialist_women"))
    for label, course, profile in cases:
        jobs.append(dict(tag=f"{label}__calm", course=course, profile=profile,
                         wind_speed=0.0, wind_from=0.0))
        for speed in (2.0, 4.0, 6.0):
            for direction in range(0, 360, 45):
                jobs.append(dict(
                    tag=f"{label}__{speed:g}ms_from{direction:03d}",
                    course=course, profile=profile,
                    wind_speed=speed, wind_from=float(direction)))
    _run_jobs(jobs, "wind", workers)
    _wind_forecast_error()


def _wind_forecast_error():
    """Rides the plan made for the forecast in slightly different wind."""
    import numpy as np
    from profiles import rider as rider_profiles
    from solver import execution, simulate

    print("wind forecast error")
    rows = []
    for label, course_name, profile_name, forecast in (
        ("flanders", "flanders_2021_men", "tt_specialist", (4.0, 225)),
        ("tokyo", "tokyo_2021_women", "tt_specialist_women", (4.0, 225)),
    ):
        profile = rider_profiles.load(profile_name)
        physics, rider = _physics(profile, course_name), profile.rider_params()
        plan_tag = f"{label}__{forecast[0]:g}ms_from{forecast[1]:03d}"
        plan = np.load(OUT / f"wind__{plan_tag}.npz")["power"]
        reopt = {r["tag"]: r for r in json.loads((OUT / "wind.json").read_text())}
        extra_path = OUT / "wind_extra.json"
        if extra_path.exists():
            reopt.update({r["tag"]: r for r in json.loads(extra_path.read_text())})
        missing = []
        for d_speed in (-1.0, 0.0, 1.0):
            for d_dir in (-45, 0, 45):
                speed = forecast[0] + d_speed
                direction = (forecast[1] + d_dir) % 360
                tag = f"{label}__{speed:g}ms_from{direction:03d}"
                if tag not in reopt:
                    missing.append(dict(tag=tag, course=course_name, profile=profile_name,
                                        wind_speed=speed, wind_from=float(direction)))
        if missing:
            old = json.loads(extra_path.read_text()) if extra_path.exists() else []
            new = _run_jobs(missing, "wind_extra_tmp", 2)
            extra_path.write_text(json.dumps(old + new, indent=1))
            reopt.update({r["tag"]: r for r in new})
        for d_speed in (-1.0, 0.0, 1.0):
            for d_dir in (-45, 0, 45):
                speed = forecast[0] + d_speed
                direction = (forecast[1] + d_dir) % 360
                grid = simulate.build_grid(_load(course_name, speed, direction), physics)
                ride = execution.ride_plan(plan, grid, physics, rider)
                row = dict(course=label, wind_speed=speed, wind_from=direction,
                           fixed_plan_time=float(ride.total_time[0]),
                           exhausted_fraction=float(ride.exhausted[0]))
                tag = f"{label}__{speed:g}ms_from{direction:03d}"
                if tag in reopt:
                    row["reoptimized_time"] = reopt[tag]["optimal_time"]
                rows.append(row)
                print("  ", row, flush=True)
    (OUT / "wind_forecast_error.json").write_text(json.dumps(rows, indent=1))


def part_deviation(workers):
    """Monte Carlo of power errors for one rider on one course."""
    import numpy as np
    from profiles import rider as rider_profiles
    from solver import execution, simulate

    print("deviation")
    tag = "tokyo__tt_specialist"
    data_path = OUT / f"courses__{tag}.npz"
    if not data_path.exists():
        _run_jobs([dict(tag=tag, course="tokyo_2021_men",
                        profile="tt_specialist", fatigue=None)], "courses_dev", 1)
        data_path = OUT / f"courses_dev__{tag}.npz"
    data = np.load(data_path)
    plan = data["power"]
    profile = rider_profiles.load("tt_specialist")
    physics, rider = _physics(profile, "tokyo_2021_men"), profile.rider_params()
    course = _load("tokyo_2021_men")
    grid = simulate.build_grid(course, physics)
    exact = execution.ride_plan(plan, grid, physics, rider)

    # Key points: the high and low point of each lap, the lap line, finish.
    half = course.length / 2
    checkpoints = {}
    for lap, (start, end) in enumerate(((0.0, half), (half, course.length)), 1):
        part = (course.distance >= start) & (course.distance < end)
        dist, ele = course.distance[part], course.elevation[part]
        top = int(np.argmax(ele))
        checkpoints[f"top of climb {lap}"] = float(dist[top])
        checkpoints[f"bottom of descent {lap}"] = float(dist[top + int(np.argmin(ele[top:]))])
        if lap == 1:
            checkpoints["end of lap 1"] = float(half)
    checkpoints["finish"] = float(course.length)
    points = np.array(list(checkpoints.values()))
    exact_splits = exact.split_times(points)[0]

    rides = 500
    scenarios = [("random 2.5%", 0.025, 0.0), ("random 5%", 0.05, 0.0),
                 ("random 10%", 0.10, 0.0), ("3% too easy", 0.05, -0.03),
                 ("3% too hard", 0.05, 0.03), ("6% too hard", 0.05, 0.06)]
    rows = []
    for name, sigma, bias in scenarios:
        errors = execution.power_noise(rides, grid.num_steps, grid.step, sigma,
                                       bias=bias, seed=1)
        batch = execution.ride_plan(plan, grid, physics, rider, relative_error=errors)
        splits = batch.split_times(points)
        row = dict(scenario=name, sigma=sigma, bias=bias,
                   exact_time=float(exact.total_time[0]),
                   mean_time=float(batch.total_time.mean()),
                   p05=float(np.percentile(batch.total_time, 5)),
                   p95=float(np.percentile(batch.total_time, 95)),
                   mean_exhausted=float(batch.exhausted.mean()),
                   splits={k: dict(exact=float(e), p05=float(np.percentile(splits[:, j], 5)),
                                   p50=float(np.percentile(splits[:, j], 50)),
                                   p95=float(np.percentile(splits[:, j], 95)))
                           for j, (k, e) in enumerate(zip(checkpoints, exact_splits))})
        rows.append(row)
        np.save(OUT / f"deviation__{name.replace(' ', '_').replace('%', 'pct')}.npy",
                batch.total_time)
        print(f"  {name:14s} mean {row['mean_time']:.1f}  5-95% "
              f"[{row['p05']:.1f}, {row['p95']:.1f}]  exhausted {row['mean_exhausted']:.3f}",
              flush=True)

    # A practical plan: hold the average target over each 1 km block.
    block = int(round(1000 / grid.step))
    smooth = plan.copy()
    for start in range(0, plan.size, block):
        part = slice(start, start + block)
        durations = np.diff(exact.time[0])[part]
        smooth[part] = np.sum(plan[part] * durations) / durations.sum()
    smooth_ride = execution.ride_plan(smooth, grid, physics, rider)
    summary = dict(scenarios=rows, checkpoints=checkpoints,
                   smoothed_1km_time=float(smooth_ride.total_time[0]),
                   smoothed_1km_exhausted=float(smooth_ride.exhausted[0]),
                   exact_time=float(exact.total_time[0]))
    np.save(OUT / "deviation__smoothed_plan.npy", smooth)
    (OUT / "deviation.json").write_text(json.dumps(summary, indent=1))
    print("  1 km blocks:", summary["smoothed_1km_time"])


def part_fatigue(workers):
    print("fatigue")
    jobs = [dict(tag="classic", course="tokyo_2021_men",
                 profile="tt_specialist", fatigue=CLASSIC)]
    jobs += [dict(tag=f"tau{time:g}", course="tokyo_2021_men",
                  profile="tt_specialist", fatigue=dict(fatigue_time=time))
             for time in (6000.0, 3000.0, 1500.0)]
    _run_jobs(jobs, "fatigue", workers)


def part_forecast(workers):
    _wind_forecast_error()


PARTS = {"courses": part_courses, "wind": part_wind, "forecast": part_forecast,
         "deviation": part_deviation, "fatigue": part_fatigue}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("parts", nargs="+", choices=list(PARTS) + ["all"])
    parser.add_argument("--no-polish", action="store_true")
    parser.add_argument("--workers", type=int, default=max(1, multiprocessing.cpu_count()))
    args = parser.parse_args()
    _setup(not args.no_polish)
    OUT.mkdir(parents=True, exist_ok=True)
    parts = list(PARTS) if "all" in args.parts else args.parts
    for part in parts:
        PARTS[part](args.workers)


if __name__ == "__main__":
    main()
