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


@dataclass(frozen=True)
class Targets:
    bmr: float
    tdee: float
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


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
    protein_g = protein_target(weight_kg, protein_g_per_kg)
    fat_g = FAT_SHARE * kcal / 9
    carbs_g = max(0.0, (kcal - 4 * protein_g - 9 * fat_g) / 4)
    return Targets(bmr, tdee_value, kcal, protein_g, carbs_g, fat_g)
