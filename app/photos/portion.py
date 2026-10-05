"""Portion estimate from a photo with the user's hand flat on the plate.

The hand gives the scale (cm per pixel at the plate's level): MediaPipe finds
the hand landmarks, the distance between the index and little-finger knuckles
is the metacarpal hand breadth, which the profile predicts from sex and height.
The food area is then measured inside the plate (pixels that are not plate
coloured, hand excluded) and turned into grams with a per-food-type surface
density. The result is a range: the height of the heap is a guess.

Only works for the photo taken from above with the hand open and flat next to
the food. Returns None when no hand is found.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.config import PROJECT_ROOT

MODEL_PATH = PROJECT_ROOT / "data" / "models" / "hand_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)

# Metacarpal hand breadth (index to little-finger knuckle) as a fraction of
# stature; anthropometric averages, men ≈ 8.7 cm at 176 cm, women ≈ 7.7 at 163.
HAND_BREADTH_RATIO = {"M": 0.0494, "F": 0.0472}

# Grams per cm² of plate covered, for a typical serving height. Keys are
# matched against the food's category / name words; "default" otherwise.
DENSITY_G_PER_CM2 = {
    "pasta": 1.0,
    "riso": 1.0,
    "cereali": 0.9,
    "legumi": 0.9,
    "patate": 0.9,
    "carne": 0.85,
    "pesce": 0.8,
    "uova": 0.8,
    "formaggio": 0.7,
    "pizza": 0.55,
    "pane": 0.35,
    "verdure cotte": 0.6,
    "insalata": 0.2,
    "frutta": 0.8,
    "default": 0.8,
}
RANGE = 0.30  # ± on the central estimate

MIN_PLATE_FRACTION = 0.08  # the plate must cover at least this share of the image


@dataclass(frozen=True)
class HandScale:
    cm_per_px: float
    breadth_px: float
    hull: np.ndarray  # polygon (N, 2) in pixels around the hand, to exclude it


@dataclass(frozen=True)
class PortionEstimate:
    cm_per_px: float
    area_cm2: float
    plate_found: bool
    grams: dict[str, tuple[int, int, int]]  # food type → (low, central, high)

    def for_type(self, key: str) -> tuple[int, int, int]:
        return self.grams.get(key, self.grams["default"])


def hand_breadth_cm(sex: str, height_cm: float) -> float:
    return HAND_BREADTH_RATIO.get(sex.upper(), HAND_BREADTH_RATIO["M"]) * height_cm


# --- hand -------------------------------------------------------------------

_landmarker = None


def _get_landmarker():
    global _landmarker
    if _landmarker is None:
        import mediapipe as mp
        from mediapipe.tasks.python import vision

        if not MODEL_PATH.is_file():
            raise FileNotFoundError(f"Modello mano mancante: {MODEL_PATH} (scaricalo da {MODEL_URL})")
        options = vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
            num_hands=1,
            min_hand_detection_confidence=0.4,
        )
        _landmarker = vision.HandLandmarker.create_from_options(options)
    return _landmarker


def detect_hand(rgb: np.ndarray, breadth_cm: float) -> HandScale | None:
    """Find one hand in an RGB uint8 image; scale from the knuckle breadth."""
    import mediapipe as mp

    result = _get_landmarker().detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    if not result.hand_landmarks:
        return None
    h, w = rgb.shape[:2]
    pts = np.array([(lm.x * w, lm.y * h) for lm in result.hand_landmarks[0]], dtype=np.float32)
    index_mcp, pinky_mcp = pts[5], pts[17]
    breadth_px = float(np.linalg.norm(index_mcp - pinky_mcp))
    if breadth_px < 10:
        return None
    import cv2

    hull = cv2.convexHull(pts.astype(np.int32)).reshape(-1, 2)
    return HandScale(cm_per_px=breadth_cm / breadth_px, breadth_px=breadth_px, hull=hull)


# --- plate and food area ------------------------------------------------------

def plate_mask(rgb: np.ndarray) -> tuple[np.ndarray, bool]:
    """A mask of the plate (largest bright, low-saturation blob), or the whole
    image when no plate-like region is found."""
    import cv2

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    bright = ((hsv[:, :, 2] > 150) & (hsv[:, :, 1] < 70)).astype(np.uint8)
    bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bright, connectivity=8)
    if n <= 1:
        return np.ones(rgb.shape[:2], dtype=bool), False
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    if stats[biggest, cv2.CC_STAT_AREA] < MIN_PLATE_FRACTION * rgb.shape[0] * rgb.shape[1]:
        return np.ones(rgb.shape[:2], dtype=bool), False
    # Fill the plate: convex hull of the bright region (the food sits inside it).
    ys, xs = np.where(labels == biggest)
    hull = cv2.convexHull(np.stack([xs, ys], axis=1).astype(np.int32))
    mask = np.zeros(rgb.shape[:2], dtype=np.uint8)
    cv2.fillConvexPoly(mask, hull, 1)
    return mask.astype(bool), True


def food_mask(rgb: np.ndarray, plate: np.ndarray, hand_hull: np.ndarray | None) -> np.ndarray:
    """Inside the plate, food is what is not plate-coloured; the hand is cut out."""
    import cv2

    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    not_plate = (hsv[:, :, 1] > 60) | (hsv[:, :, 2] < 140)
    mask = not_plate & plate
    if hand_hull is not None:
        cut = np.zeros(rgb.shape[:2], dtype=np.uint8)
        cv2.fillConvexPoly(cut, hand_hull.astype(np.int32), 1)
        cut = cv2.dilate(cut, np.ones((25, 25), np.uint8))
        mask &= cut == 0
    mask = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    return mask.astype(bool)


# --- grams ------------------------------------------------------------------------

def grams_from_area(area_cm2: float) -> dict[str, tuple[int, int, int]]:
    out = {}
    for key, density in DENSITY_G_PER_CM2.items():
        g = area_cm2 * density
        out[key] = (int(round(g * (1 - RANGE) / 5) * 5), int(round(g / 5) * 5), int(round(g * (1 + RANGE) / 5) * 5))
    return out


def density_key(food_name: str, category: str | None) -> str:
    text = f"{food_name} {category or ''}".lower()
    if "insalata" in text or "lattuga" in text or "rucola" in text:
        return "insalata"
    if "pizza" in text:
        return "pizza"
    if "pane" in text and "panna" not in text:
        return "pane"
    for key in ("pasta", "riso", "cereali", "legumi", "patate", "carne", "pesce", "uova", "formaggio", "frutta"):
        if key in text:
            return key
    if "verdur" in text:
        return "verdure cotte"
    return "default"


def estimate_portion(rgb: np.ndarray, sex: str, height_cm: float) -> PortionEstimate | None:
    hand = detect_hand(rgb, hand_breadth_cm(sex, height_cm))
    if hand is None:
        return None
    plate, found = plate_mask(rgb)
    food = food_mask(rgb, plate, hand.hull)
    area_cm2 = float(food.sum()) * hand.cm_per_px ** 2
    return PortionEstimate(hand.cm_per_px, area_cm2, found, grams_from_area(area_cm2))
