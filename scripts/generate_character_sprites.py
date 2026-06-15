from pathlib import Path

from PIL import Image, ImageChops, ImageColor, ImageDraw


FRAME_WIDTH = 32
FRAME_HEIGHT = 48
DIRECTIONS = ("down", "left", "right", "up")
STEPS = (-1, 0, 1)
OUTPUT_DIR = Path(__file__).parents[1] / "frontend" / "static" / "assets" / "player"

OUTLINE = "#17202a"
SKIN = "#e8aa78"
SKIN_LIGHT = "#f4c18f"
SHOE = "#252d36"
WHITE = "#fff2c6"
TINT_DARK = "#737373"
TINT_MID = "#b8b8b8"
TINT_LIGHT = "#f2f2f2"
PACK_DARK = "#75551e"
PACK_MID = "#bd8e2f"
PACK_LIGHT = "#e8bd55"


def rect(draw, box, fill, outline=None):
    draw.rectangle(box, fill=fill, outline=outline)


def polygon(draw, points, fill, outline=None):
    draw.polygon(points, fill=fill)
    if outline:
        draw.line([*points, points[0]], fill=outline, width=1)


def frame_origin(direction_index, step_index):
    return step_index * FRAME_WIDTH, direction_index * FRAME_HEIGHT


def draw_body(draw, ox, oy, direction, step):
    bob = 1 if step else 0
    y = oy + bob
    if direction == "down":
        rect(draw, (ox + 9, y + 5, ox + 22, y + 18), SKIN, OUTLINE)
        rect(draw, (ox + 11, y + 6, ox + 20, y + 10), SKIN_LIGHT)
        rect(draw, (ox + 12, y + 19, ox + 19, y + 22), SKIN, OUTLINE)
        rect(draw, (ox + 11, y + 11, ox + 12, y + 12), OUTLINE)
        rect(draw, (ox + 19, y + 11, ox + 20, y + 12), OUTLINE)
        rect(draw, (ox + 14, y + 15, ox + 17, y + 15), "#9b523f")
        rect(draw, (ox + 4, y + 25, ox + 7, y + 31), SKIN, OUTLINE)
        rect(draw, (ox + 24, y + 25, ox + 27, y + 31), SKIN, OUTLINE)
    elif direction == "up":
        rect(draw, (ox + 9, y + 5, ox + 22, y + 18), SKIN, OUTLINE)
        rect(draw, (ox + 12, y + 19, ox + 19, y + 22), SKIN, OUTLINE)
        rect(draw, (ox + 4, y + 25, ox + 7, y + 31), SKIN, OUTLINE)
        rect(draw, (ox + 24, y + 25, ox + 27, y + 31), SKIN, OUTLINE)
    else:
        facing_right = direction == "right"
        rect(draw, (ox + 10, y + 5, ox + 21, y + 18), SKIN, OUTLINE)
        nose_x = ox + (22 if facing_right else 9)
        rect(draw, (nose_x, y + 11, nose_x, y + 13), SKIN_LIGHT, OUTLINE)
        eye_x = ox + (19 if facing_right else 11)
        rect(draw, (eye_x, y + 10, eye_x + 1, y + 11), OUTLINE)
        rect(draw, (ox + 12, y + 19, ox + 18, y + 22), SKIN, OUTLINE)
        hand_x = ox + (23 if facing_right else 6)
        rect(draw, (hand_x, y + 26, hand_x + 3, y + 31), SKIN, OUTLINE)

    left_lift = 1 if step < 0 else 0
    right_lift = 1 if step > 0 else 0
    rect(draw, (ox + 8, y + 42 - left_lift, ox + 14, y + 46 - left_lift), SHOE, OUTLINE)
    rect(draw, (ox + 17, y + 42 - right_lift, ox + 23, y + 46 - right_lift), SHOE, OUTLINE)


def draw_gear_back(draw, ox, oy, direction, step):
    bob = 1 if step else 0
    y = oy + bob
    if direction == "up":
        rect(draw, (ox + 7, y + 20, ox + 24, y + 35), PACK_DARK, OUTLINE)
        rect(draw, (ox + 9, y + 21, ox + 22, y + 31), PACK_MID)
        rect(draw, (ox + 11, y + 22, ox + 20, y + 24), PACK_LIGHT)
    elif direction == "left":
        rect(draw, (ox + 18, y + 21, ox + 26, y + 35), PACK_DARK, OUTLINE)
        rect(draw, (ox + 20, y + 23, ox + 25, y + 31), PACK_MID)
    elif direction == "right":
        rect(draw, (ox + 5, y + 21, ox + 13, y + 35), PACK_DARK, OUTLINE)
        rect(draw, (ox + 6, y + 23, ox + 11, y + 31), PACK_MID)
    else:
        rect(draw, (ox + 21, y + 22, ox + 27, y + 34), PACK_DARK, OUTLINE)
        rect(draw, (ox + 22, y + 24, ox + 26, y + 31), PACK_MID)


def draw_pants(draw, ox, oy, direction, step):
    bob = 1 if step else 0
    y = oy + bob
    left_lift = 1 if step < 0 else 0
    right_lift = 1 if step > 0 else 0
    rect(draw, (ox + 9, y + 34, ox + 22, y + 39), TINT_DARK, OUTLINE)
    rect(draw, (ox + 9, y + 35, ox + 14, y + 43 - left_lift), TINT_MID, OUTLINE)
    rect(draw, (ox + 17, y + 35, ox + 22, y + 43 - right_lift), TINT_MID, OUTLINE)
    if direction in ("left", "right"):
        rect(draw, (ox + 16, y + 36, ox + 22, y + 42 - right_lift), TINT_DARK)
    else:
        rect(draw, (ox + 10, y + 36, ox + 11, y + 41 - left_lift), TINT_LIGHT)
        rect(draw, (ox + 18, y + 36, ox + 19, y + 41 - right_lift), TINT_LIGHT)


def draw_shirt(draw, ox, oy, direction, step):
    bob = 1 if step else 0
    y = oy + bob
    arm_shift = step
    rect(draw, (ox + 9, y + 21, ox + 22, y + 35), TINT_MID, OUTLINE)
    rect(draw, (ox + 10, y + 22, ox + 12, y + 33), TINT_LIGHT)
    if direction == "up":
        rect(draw, (ox + 8, y + 22, ox + 10, y + 33), TINT_DARK, OUTLINE)
        rect(draw, (ox + 21, y + 22, ox + 23, y + 33), TINT_DARK, OUTLINE)
    elif direction == "left":
        polygon(draw, [(ox + 10, y + 22), (ox + 7, y + 24 + arm_shift), (ox + 6, y + 31 + arm_shift), (ox + 9, y + 32), (ox + 12, y + 25)], TINT_MID, OUTLINE)
        polygon(draw, [(ox + 21, y + 22), (ox + 24, y + 25 - arm_shift), (ox + 23, y + 31 - arm_shift), (ox + 20, y + 30)], TINT_DARK, OUTLINE)
    elif direction == "right":
        polygon(draw, [(ox + 21, y + 22), (ox + 24, y + 24 - arm_shift), (ox + 25, y + 31 - arm_shift), (ox + 22, y + 32), (ox + 19, y + 25)], TINT_MID, OUTLINE)
        polygon(draw, [(ox + 10, y + 22), (ox + 7, y + 25 + arm_shift), (ox + 8, y + 31 + arm_shift), (ox + 11, y + 30)], TINT_DARK, OUTLINE)
    else:
        polygon(draw, [(ox + 9, y + 22), (ox + 5, y + 24 + arm_shift), (ox + 5, y + 30 + arm_shift), (ox + 8, y + 31), (ox + 11, y + 25)], TINT_MID, OUTLINE)
        polygon(draw, [(ox + 22, y + 22), (ox + 26, y + 24 - arm_shift), (ox + 26, y + 30 - arm_shift), (ox + 23, y + 31), (ox + 20, y + 25)], TINT_DARK, OUTLINE)
        polygon(draw, [(ox + 13, y + 21), (ox + 16, y + 25), (ox + 19, y + 21)], WHITE, OUTLINE)


def draw_hair(draw, ox, oy, direction, step):
    bob = 1 if step else 0
    y = oy + bob
    if direction == "up":
        rect(draw, (ox + 8, y + 4, ox + 23, y + 16), TINT_DARK, OUTLINE)
        rect(draw, (ox + 10, y + 5, ox + 20, y + 8), TINT_LIGHT)
        rect(draw, (ox + 8, y + 13, ox + 10, y + 19), TINT_DARK, OUTLINE)
        rect(draw, (ox + 21, y + 13, ox + 23, y + 19), TINT_DARK, OUTLINE)
    elif direction == "left":
        polygon(draw, [(ox + 9, y + 5), (ox + 21, y + 4), (ox + 23, y + 8), (ox + 21, y + 12), (ox + 18, y + 9), (ox + 9, y + 10)], TINT_MID, OUTLINE)
        rect(draw, (ox + 18, y + 6, ox + 21, y + 8), TINT_LIGHT)
        rect(draw, (ox + 20, y + 13, ox + 22, y + 19), TINT_DARK, OUTLINE)
    elif direction == "right":
        polygon(draw, [(ox + 22, y + 5), (ox + 10, y + 4), (ox + 8, y + 8), (ox + 10, y + 12), (ox + 13, y + 9), (ox + 22, y + 10)], TINT_MID, OUTLINE)
        rect(draw, (ox + 10, y + 6, ox + 13, y + 8), TINT_LIGHT)
        rect(draw, (ox + 9, y + 13, ox + 11, y + 19), TINT_DARK, OUTLINE)
    else:
        polygon(draw, [(ox + 8, y + 10), (ox + 10, y + 5), (ox + 14, y + 3), (ox + 21, y + 5), (ox + 23, y + 9), (ox + 21, y + 11), (ox + 18, y + 8), (ox + 15, y + 11), (ox + 12, y + 8), (ox + 10, y + 13)], TINT_MID, OUTLINE)
        rect(draw, (ox + 12, y + 5, ox + 18, y + 6), TINT_LIGHT)
        rect(draw, (ox + 9, y + 12, ox + 11, y + 19), TINT_DARK, OUTLINE)
        rect(draw, (ox + 20, y + 11, ox + 22, y + 19), TINT_DARK, OUTLINE)


def draw_gear_front(draw, ox, oy, direction, step):
    bob = 1 if step else 0
    y = oy + bob
    if direction == "down":
        rect(draw, (ox + 21, y + 23, ox + 23, y + 32), PACK_DARK, OUTLINE)
        rect(draw, (ox + 22, y + 25, ox + 23, y + 27), PACK_LIGHT)
    elif direction == "up":
        rect(draw, (ox + 10, y + 22, ox + 11, y + 30), PACK_LIGHT)
        rect(draw, (ox + 20, y + 22, ox + 21, y + 30), PACK_LIGHT)
    elif direction == "left":
        rect(draw, (ox + 18, y + 22, ox + 19, y + 31), PACK_LIGHT)
    else:
        rect(draw, (ox + 12, y + 22, ox + 13, y + 31), PACK_LIGHT)


DRAWERS = {
    "body": draw_body,
    "gear-back": draw_gear_back,
    "pants": draw_pants,
    "shirt": draw_shirt,
    "hair": draw_hair,
    "gear-front": draw_gear_front,
}

PALETTES = {
    "shirt": {
        "red": "#d94b48", "blue": "#3f71b5", "green": "#4d8d59",
        "yellow": "#e1b840", "purple": "#765495", "teal": "#398b87",
    },
    "pants": {
        "navy": "#263b60", "charcoal": "#3d4148", "brown": "#6f4d3b",
        "olive": "#5d673f", "blue": "#365f86", "plum": "#61405d",
    },
    "hair": {
        "black": "#1d2025", "dark_brown": "#3b271f", "brown": "#70462c",
        "blond": "#c99a45", "auburn": "#8a3f2c",
    },
}


def tint_atlas(atlas, color):
    solid = Image.new("RGB", atlas.size, ImageColor.getrgb(color))
    shaded = ImageChops.multiply(atlas.convert("RGB"), solid)
    return Image.merge("RGBA", (*shaded.split(), atlas.getchannel("A")))


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, drawer in DRAWERS.items():
        atlas = Image.new("RGBA", (FRAME_WIDTH * 3, FRAME_HEIGHT * 4), (0, 0, 0, 0))
        draw = ImageDraw.Draw(atlas)
        for direction_index, direction in enumerate(DIRECTIONS):
            for step_index, step in enumerate(STEPS):
                drawer(draw, *frame_origin(direction_index, step_index), direction, step)
        if name in PALETTES:
            for color_name, color in PALETTES[name].items():
                tint_atlas(atlas, color).save(OUTPUT_DIR / f"student-{name}-{color_name}.png", optimize=True)
        else:
            atlas.save(OUTPUT_DIR / f"student-{name}.png", optimize=True)


if __name__ == "__main__":
    main()
