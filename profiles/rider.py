"""Loads rider profiles from JSON into a Python class.

A profile is everything that belongs to one rider and their bike: masses,
drag area, rolling resistance, and the stamina parameters. The
physics and power models keep their own parameter classes, and a profile
fills them in:

    profile = rider.load("tt_specialist")
    physics = profile.physics_params()
    power = profile.rider_params()
"""

import dataclasses
import json
import pathlib

from physics_model import params as physics_params
from power_model import params as rider_params

PROFILE_DIR = pathlib.Path(__file__).resolve().parent

_DEFAULT_PHYSICS = physics_params.PhysicsParams()

# JSON key -> RiderProfile field, for the top level and the "power" block.
_TOP_LEVEL_KEYS = {
    "name": "name",
    "description": "description",
    "rider_mass_kg": "rider_mass",
    "bike_mass_kg": "bike_mass",
    "cda_m2": "cda",
    "crr": "crr",
}
_POWER_KEYS = {
    "lt1_w": "lt1",
    "lt2_w": "lt2",
    "w_prime_j": "w_prime",
    "p_max_w": "p_max",
    "recovery_alpha": "alpha",
    "recovery_beta": "beta",
    "fatigue_exponent": "fatigue_exponent",
    "fatigue_time_s": "fatigue_time",
    "w_prime_work_scale_j_per_kg": "work_scale",
    "best_efforts": "best_efforts",
}
_OPTIONAL_FIELDS = (
    "description", "alpha", "beta", "fatigue_exponent", "fatigue_time",
    "work_scale", "best_efforts",
)
# Fields that are not single positive numbers.
_UNCHECKED_FIELDS = ("name", "description", "best_efforts")


@dataclasses.dataclass(frozen=True)
class RiderProfile:
    """One rider and their bike.

    Attributes:
        name: Display name of the profile.
        rider_mass: Body mass of the rider [kg].
        bike_mass: Mass of the bike and all equipment [kg].
        cda: Drag area C_d A in the rider's race position [m^2].
        crr: Rolling resistance coefficient of the tyres [-].
        lt1: First lactate threshold, LT1 [W].
        lt2: Second lactate threshold, LT2 [W], taken as the critical power
            of the fresh rider.
        w_prime: Work capacity above critical power when fresh, W'_0 [J].
        p_max: Hard cap on instantaneous power [W].
        alpha: Recovery rate coefficient [-].
        beta: Recovery saturation exponent [-].
        fatigue_exponent: How steeply fatigue grows with intensity [-].
        fatigue_time: Fatigue at which critical power has lost 63% of the
            span between LT2 and LT1 [s].
        work_scale: Work done per kilogram of body mass at which W' has
            fallen to 37% of its fresh value [J/kg].
        best_efforts: Measured best efforts the power numbers were fitted
            to, as (duration [s], power [W]) pairs. Kept for reference and
            for checking the fit; the model does not read them.
        description: One line on what kind of rider this is.
    """

    name: str
    rider_mass: float
    bike_mass: float
    cda: float
    crr: float
    lt1: float
    lt2: float
    w_prime: float
    p_max: float
    alpha: float = 1.0
    beta: float = 1.0
    fatigue_exponent: float = 1.7
    fatigue_time: float = 3000.0
    work_scale: float = 57_400.0
    best_efforts: tuple[tuple[float, float], ...] = ()
    description: str = ""

    def __post_init__(self):
        for field in dataclasses.fields(self):
            value = getattr(self, field.name)
            if field.name not in _UNCHECKED_FIELDS and value <= 0:
                raise ValueError(f"{field.name} must be positive: {value}.")
        if not self.lt1 < self.lt2 <= self.p_max:
            raise ValueError("Need lt1 < lt2 <= p_max.")

    @property
    def total_mass(self) -> float:
        """Combined mass of rider and bike, m [kg]."""
        return self.rider_mass + self.bike_mass

    @property
    def cp(self) -> float:
        """Critical power of the fresh rider, CP_0 = LT2 [W]."""
        return self.lt2

    @property
    def cp_per_kg(self) -> float:
        """Critical power per kilogram of body mass [W/kg]."""
        return self.cp / self.rider_mass

    def physics_params(
        self, base: physics_params.PhysicsParams = _DEFAULT_PHYSICS
    ) -> physics_params.PhysicsParams:
        """Builds the physics parameters for this rider.

        Args:
            base: Supplies everything that is not the rider's: gravity, air
                density, grip, and braking.

        Returns:
            `base` with the mass, drag area, and rolling resistance of this
            profile.
        """
        return dataclasses.replace(
            base, mass=self.total_mass, cda=self.cda, crr=self.crr
        )

    def rider_params(self) -> rider_params.RiderParams:
        """Builds the stamina parameters for this rider."""
        return rider_params.RiderParams(
            lt1=self.lt1,
            lt2=self.lt2,
            w_prime=self.w_prime,
            p_max=self.p_max,
            alpha=self.alpha,
            beta=self.beta,
            fatigue_exponent=self.fatigue_exponent,
            fatigue_time=self.fatigue_time,
            work_capacity=self.work_scale * self.rider_mass,
        )


def available() -> list[str]:
    """Lists the names of the profiles shipped in this folder."""
    return sorted(path.stem for path in PROFILE_DIR.glob("*.json"))


def _rename(block: dict, keys: dict[str, str], where: str) -> dict:
    """Maps JSON keys to field names, rejecting unknown keys."""
    unknown = sorted(set(block) - set(keys))
    if unknown:
        raise ValueError(f"Unknown keys in {where}: {', '.join(unknown)}.")
    return {keys[key]: value for key, value in block.items()}


def load(name_or_path: str | pathlib.Path) -> RiderProfile:
    """Loads a rider profile.

    Args:
        name_or_path: Either the name of a profile in this folder, such as
            "tt_specialist", or the path of any profile JSON file.

    Returns:
        The profile.

    Raises:
        FileNotFoundError: If there is no such profile.
        ValueError: If the file has unknown, missing, or invalid entries.
    """
    path = pathlib.Path(name_or_path)
    if path.suffix != ".json":
        path = PROFILE_DIR / f"{path.name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No profile at {path}. Available: {', '.join(available())}."
        )
    data = json.loads(path.read_text())
    power = data.pop("power", {})
    fields = _rename(data, _TOP_LEVEL_KEYS, path.name)
    fields.update(_rename(power, _POWER_KEYS, f"{path.name} 'power'"))
    if "best_efforts" in fields:
        fields["best_efforts"] = tuple(
            (float(duration), float(watts))
            for duration, watts in fields["best_efforts"]
        )

    required = {
        field.name for field in dataclasses.fields(RiderProfile)
    } - set(_OPTIONAL_FIELDS)
    json_keys = {field: key for key, field in _TOP_LEVEL_KEYS.items()}
    json_keys.update({field: key for key, field in _POWER_KEYS.items()})
    missing = sorted(json_keys[field] for field in required - set(fields))
    if missing:
        raise ValueError(f"{path.name} is missing: {', '.join(missing)}.")
    return RiderProfile(**fields)
