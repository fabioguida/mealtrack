"""Daily targets from the profile (HANDOVER.md §5).

BMR by Mifflin-St Jeor, TDEE = BMR × activity factor, kcal target = TDEE − deficit,
protein target = g per kg × weight. Carbs and fat are informative references:
fat at 30 % of the kcal target, carbs with what is left.
"""

from dataclasses import dataclass

ACTIVITY_FACTORS = {
    "sedentario": 1.2,
    "leggero": 1.375,
    "moderato": 1.55,
    "attivo": 1.725,
    "molto_attivo": 1.9,
}

FAT_SHARE = 0.30  # of the kcal target, for the informative fat reference

# The user chooses a pace; the app derives the deficit and the protein level.
KCAL_PER_KG_FAT = 7700
PACES = {  # kg per week → label
    0.0: "Mantenere il peso",
    0.25: "Perdere 0,25 kg a settimana (lento)",
    0.5: "Perdere 0,5 kg a settimana (consigliato)",
    0.75: "Perdere 0,75 kg a settimana (deciso)",
}
PROTEIN_G_PER_KG_LOSS = 1.5
PROTEIN_G_PER_KG_MAINTAIN = 1.2


def deficit_for(kg_per_week: float) -> float:
    """Daily kcal deficit to lose `kg_per_week`."""
    return kg_per_week * KCAL_PER_KG_FAT / 7


def protein_g_per_kg_for(kg_per_week: float) -> float:
    return PROTEIN_G_PER_KG_LOSS if kg_per_week > 0 else PROTEIN_G_PER_KG_MAINTAIN


@dataclass(frozen=True)
class Targets:
    bmr: float
    tdee: float
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    deficit_kcal: float = 0.0        # the deficit actually applied
    protein_g_per_kg: float = 0.0
    floored: bool = False            # True when the BMR floor reduced the deficit


def bmr_mifflin(sex: str, weight_kg: float, height_cm: float, age: int) -> float:
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex.upper() == "M" else base - 161


def tdee(bmr: float, activity_factor: float) -> float:
    return bmr * activity_factor


def kcal_target(tdee_value: float, deficit_kcal: float) -> float:
    return tdee_value - deficit_kcal


def protein_target(weight_kg: float, g_per_kg: float) -> float:
    return weight_kg * g_per_kg


def daily_targets(
    sex: str,
    age: int,
    height_cm: float,
    weight_kg: float,
    activity: str,
    deficit_kcal: float,
    protein_g_per_kg: float,
) -> Targets:
    bmr = bmr_mifflin(sex, weight_kg, height_cm, age)
    tdee_value = tdee(bmr, ACTIVITY_FACTORS[activity])
    kcal = kcal_target(tdee_value, deficit_kcal)
    floored = kcal < bmr
    if floored:
        # Never below the basal metabolism: the deficit shrinks instead.
        kcal = bmr
        deficit_kcal = tdee_value - bmr
    protein_g = protein_target(weight_kg, protein_g_per_kg)
    fat_g = FAT_SHARE * kcal / 9
    carbs_g = max(0.0, (kcal - 4 * protein_g - 9 * fat_g) / 4)
    return Targets(bmr, tdee_value, kcal, protein_g, carbs_g, fat_g, deficit_kcal, protein_g_per_kg, floored)
