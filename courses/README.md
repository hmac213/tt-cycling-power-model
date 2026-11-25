# Courses

| File | What it is | Source |
| --- | --- | --- |
| `tokyo_2021_men.gpx` | 2021 Olympic ITT, men (two laps, 44 km) | RideWithGPS route [36837877](https://ridewithgps.com/routes/36837877), "Tokyo 2020 Men Elite ITT (copy)" |
| `tokyo_2021_women.gpx` | 2021 Olympic ITT, women (one lap, 22 km) | RideWithGPS trip [71637773](https://ridewithgps.com/trips/71637773), "Tokyo 2020 Women Elite ITT" |
| `flanders_2021_men.gpx` | 2021 UCI Worlds ITT, men, Knokke-Heist to Bruges (43.3 km official) | RideWithGPS route [37543143](https://ridewithgps.com/routes/37543143), "tijdrit WK" |
| `flanders_2021_women.gpx` | 2021 UCI Worlds ITT, women, Knokke-Heist to Bruges (30.3 km) | RideWithGPS route [37537619](https://ridewithgps.com/routes/37537619), "Flanders 2021 WE ITT" |
| `custom_loop.gpx` | Our own 12 km loop: 7 sharp corners, a 7% climb, finish on the start line | `python -m courses.make_race_gpx` |
| `flat`, `hill`, `climb`, `rolling`, `technical` | Synthetic test courses | `python -m courses.make_demo_gpx` |

The four championship files are user-made routes, exported as GPX from
RideWithGPS. They are not official organiser files. We checked each against
the published course:

| Course | Length (model) | Official | Climbing (model) | Published |
| --- | --- | --- | --- | --- |
| Tokyo men | 43.9 km | 44.2 km | 747 m | 746 m (ProCyclingStats), 846 m (Cyclingstage) |
| Tokyo women | 22.0 km | 22.1 km | 379 m | 380 m (ProCyclingStats), 423 m (Cyclingstage) |
| Flanders men | 43.8 km | 43.3 km | 48 m | 78 m (Sporza) |
| Flanders women | 30.3 km | 30.3 km | 8 m | 54 m (Sporza) |

Both Tokyo files start and finish at Fuji International Speedway. Both
Flanders files start on the Knokke-Heist seafront and finish at 't Zand in
Bruges. The men's Flanders route is 1% longer than the official distance.
The Flanders climbing differs because the published figures count bridges
and small rises that map elevation smooths away. On a course this flat,
that changes the result by very little.

## Loading the real courses

The elevations in these files come from a map elevation model, not from GPS,
and the files repeat some points with slightly different heights. The
automatic noise estimate then comes out far too small, the spline follows
the steps, and it reports grades over 100%. Load them with
`sigma_ele=1.0` (about the vertical accuracy of map elevation data):

```python
course = gpx.load_gpx("courses/tokyo_2021_men.gpx", sigma_ele=1.0)
```

`analysis/run_analysis.py` does this automatically for these four files.
