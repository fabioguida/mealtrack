"""Calories burned by activity: kcal = MET × weight (kg) × hours (HANDOVER.md §5).

MET values from the Compendium of Physical Activities (Ainsworth et al., 2011
update); the code in each row is the Compendium activity code.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Activity:
    label: str
    met: float
    compendium_code: str


MET_TABLE: dict[str, Activity] = {
    "camminata": Activity("Camminata (passo normale, 4.8 km/h)", 3.5, "17190"),
    "camminata_veloce": Activity("Camminata veloce (5.6 km/h)", 4.3, "17200"),
    "corsa_lenta": Activity("Corsa lenta (8 km/h)", 8.3, "12020"),
    "corsa": Activity("Corsa (10 km/h)", 9.8, "12050"),
    "bici": Activity("Bicicletta (moderata, 19–22 km/h)", 8.0, "01040"),
    "bici_tranquilla": Activity("Bicicletta tranquilla (<16 km/h)", 4.0, "01010"),
    "nuoto": Activity("Nuoto (vasche, moderato)", 5.8, "18240"),
    "palestra": Activity("Palestra (pesi, generale)", 3.5, "02050"),
    "palestra_intensa": Activity("Palestra (pesi, intensa)", 6.0, "02052"),
    "tennis": Activity("Tennis (singolo)", 7.3, "15675"),
    "tennis_doppio": Activity("Tennis (doppio)", 4.5, "15660"),
    "calcio": Activity("Calcio (amatoriale)", 7.0, "15605"),
    "escursione": Activity("Escursione in montagna", 6.0, "17080"),
    "yoga": Activity("Yoga", 2.5, "02150"),
    "pilates": Activity("Pilates", 3.0, "02105"),
}


def kcal_burned(met: float, weight_kg: float, minutes: float) -> float:
    return met * weight_kg * minutes / 60.0


def kcal_for(activity: str, weight_kg: float, minutes: float) -> float:
    """Raises KeyError for an activity not in the table."""
    return kcal_burned(MET_TABLE[activity].met, weight_kg, minutes)
