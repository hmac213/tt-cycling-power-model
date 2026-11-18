"""Loads rider profiles from JSON into a Python class.

A profile is everything that belongs to one rider and their bike: masses,
drag area, rolling resistance, and the Critical Power parameters. The
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
    "cp_w": "cp",
    "w_prime_j": "w_prime",
    "p_max_w": "p_max",
    "recovery_alpha": "alpha",
    "recovery_beta": "beta",
}
_OPTIONAL_FIELDS = ("description", "alpha", "beta")
_TEXT_FIELDS = ("name", "description")


@dataclasses.dataclass(frozen=True)
class RiderProfile:
    """One rider and their bike.

    Attributes:
        name: Display name of the profile.
        rider_mass: Body mass of the rider [kg].
        bike_mass: Mass of the bike and all equipment [kg].
        cda: Drag area C_d A in the rider's race position [m^2].
        crr: Rolling resistance coefficient of the tyres [-].
        cp: Critical power CP [W].
        w_prime: Anaerobic work capacity above CP, W' [J].
        p_max: Hard cap on instantaneous power [W].
        alpha: Recovery rate coefficient [-].
        beta: Recovery saturation exponent [-].
        description: One line on what kind of rider this is.
    """

    name: str
    rider_mass: float
    bike_mass: float
    cda: float
    crr: float
    cp: float
    w_prime: float
    p_max: float
    alpha: float = 1.0
    beta: float = 1.0
    description: str = ""

    def __post_init__(self):
        for field in dataclasses.fields(self):
            value = getattr(self, field.name)
            if field.name not in _TEXT_FIELDS and value <= 0:
                raise ValueError(f"{field.name} must be positive: {value}.")
        if self.p_max < self.cp:
            raise ValueError("p_max must be at least cp.")

    @property
    def total_mass(self) -> float:
        """Combined mass of rider and bike, m [kg]."""
        return self.rider_mass + self.bike_mass

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
        """Builds the Critical Power parameters for this rider."""
        return rider_params.RiderParams(
            cp=self.cp,
            w_prime=self.w_prime,
            p_max=self.p_max,
            alpha=self.alpha,
            beta=self.beta,
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

    required = {
        field.name for field in dataclasses.fields(RiderProfile)
    } - set(_OPTIONAL_FIELDS)
    json_keys = {field: key for key, field in _TOP_LEVEL_KEYS.items()}
    json_keys.update({field: key for key, field in _POWER_KEYS.items()})
    missing = sorted(json_keys[field] for field in required - set(fields))
    if missing:
        raise ValueError(f"{path.name} is missing: {', '.join(missing)}.")
    return RiderProfile(**fields)
