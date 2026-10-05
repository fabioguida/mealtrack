"""Draw the flat PNG icons and the plate-face mascot used in the emails.

Email clients do not render SVG, so these are PNGs (128 px, shown at 64 px)
in the app's palette, drawn with Pillow so they can be regenerated any time:
    python scripts/make_email_icons.py
Output: app/static/img/email/*.png
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "img" / "email"
NAVY, ACCENT, OK, OVER, MUTED, PAPER, WHITE = "#0F2A44", "#F5D35A", "#2E8B57", "#C8322B", "#56646F", "#F4F6F8", "#FFFFFF"
S = 128  # canvas


def canvas():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / f"{name}.png", optimize=True)


def icon_cart():
    img, d = canvas()
    d.rounded_rectangle((28, 40, 108, 86), radius=10, fill=ACCENT)
    d.line((14, 28, 30, 28, 44, 86), fill=NAVY, width=8, joint="curve")
    d.ellipse((44, 96, 62, 114), fill=NAVY)
    d.ellipse((86, 96, 104, 114), fill=NAVY)
    d.line((40, 60, 100, 60), fill=NAVY, width=4)
    save(img, "cart")


def icon_chart():
    img, d = canvas()
    for i, (h, c) in enumerate([(40, MUTED), (62, OK), (50, OK), (80, ACCENT)]):
        x = 20 + i * 26
        d.rounded_rectangle((x, 110 - h, x + 18, 110), radius=4, fill=c)
    d.line((14, 114, 114, 114), fill=NAVY, width=4)
    save(img, "chart")


def icon_flame():
    img, d = canvas()
    d.polygon([(64, 10), (92, 50), (98, 86), (64, 118), (30, 86), (36, 50)], fill=OVER)
    d.polygon([(64, 46), (80, 72), (82, 92), (64, 108), (46, 92), (48, 72)], fill=ACCENT)
    save(img, "flame")


def icon_scale():
    img, d = canvas()
    d.rounded_rectangle((16, 36, 112, 112), radius=14, fill=NAVY)
    d.pieslice((36, 46, 92, 102), 180, 360, fill=WHITE)
    d.line((64, 74, 80, 56), fill=OVER, width=5)
    d.rounded_rectangle((28, 22, 100, 36), radius=6, fill=MUTED)
    save(img, "scale")


def icon_plate():
    img, d = canvas()
    d.ellipse((10, 24, 118, 104), fill=WHITE, outline=MUTED, width=3)
    d.ellipse((26, 36, 102, 92), fill=PAPER, outline="#DCE2E7", width=2)
    d.ellipse((40, 48, 88, 82), fill=ACCENT)
    d.ellipse((50, 54, 60, 64), fill=OVER)
    d.ellipse((70, 60, 80, 70), fill=OK)
    save(img, "plate")


def icon_star():
    img, d = canvas()
    import math

    pts = []
    for i in range(10):
        r = 54 if i % 2 == 0 else 24
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((64 + r * math.cos(a), 66 + r * math.sin(a)))
    d.polygon(pts, fill=ACCENT, outline=NAVY)
    save(img, "star")


def icon_wave():
    img, d = canvas()
    # a hand waving: palm + four fingers
    d.rounded_rectangle((40, 56, 92, 108), radius=14, fill="#F1C9A5", outline="#D9A784", width=3)
    for x in (44, 58, 72, 86):
        d.rounded_rectangle((x - 6, 22 if x in (58, 72) else 30, x + 6, 64), radius=6, fill="#F1C9A5", outline="#D9A784", width=3)
    d.arc((96, 20, 124, 48), 300, 80, fill=NAVY, width=4)
    d.arc((104, 10, 128, 58), 300, 80, fill=NAVY, width=4)
    save(img, "wave")


def mascot(mood: str):
    """A plate with a face: happy (on target), sweaty (over), sleepy (no log), party (milestone)."""
    img, d = canvas()
    d.ellipse((8, 14, 120, 114), fill=WHITE, outline=MUTED, width=3)
    d.ellipse((22, 24, 106, 104), fill=PAPER, outline="#DCE2E7", width=2)
    eye_y = 56
    if mood == "sleepy":
        d.line((42, eye_y, 58, eye_y), fill=NAVY, width=5)
        d.line((70, eye_y, 86, eye_y), fill=NAVY, width=5)
        d.arc((50, 66, 78, 86), 0, 180, fill=NAVY, width=4)  # small flat mouth
        d.text((92, 18), "z", fill=NAVY)
        d.text((100, 8), "Z", fill=NAVY)
    else:
        d.ellipse((42, eye_y - 7, 56, eye_y + 7), fill=NAVY)
        d.ellipse((72, eye_y - 7, 86, eye_y + 7), fill=NAVY)
        if mood == "happy":
            d.arc((44, 56, 84, 92), 20, 160, fill=NAVY, width=5)
        elif mood == "sweaty":
            d.arc((48, 74, 80, 96), 200, 340, fill=NAVY, width=5)  # worried mouth
            d.ellipse((96, 40, 106, 56), fill="#7FB3E6")              # drop
        elif mood == "party":
            d.chord((44, 56, 84, 92), 20, 160, fill=OVER, outline=NAVY, width=3)
            d.polygon([(28, 30), (48, 16), (44, 40)], fill=ACCENT, outline=NAVY)  # party hat
            for x, y, c in ((100, 24, OK), (108, 40, OVER), (16, 60, ACCENT), (112, 70, NAVY)):
                d.ellipse((x, y, x + 6, y + 6), fill=c)
    save(img, f"face-{mood}")


if __name__ == "__main__":
    for fn in (icon_cart, icon_chart, icon_flame, icon_scale, icon_plate, icon_star, icon_wave):
        fn()
    for mood in ("happy", "sweaty", "sleepy", "party"):
        mascot(mood)
    print(f"icons written to {OUT}")
