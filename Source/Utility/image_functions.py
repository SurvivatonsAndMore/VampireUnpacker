import re
from pathlib import Path
from typing import Iterable

from PIL import ImageOps, ImageText, ImageFont, Image as PILImage
from PIL.Image import Resampling, Transpose, Image

from Source.Utility.constants import PROGRESS_BAR_FUNC_TYPE, PROGRESS_BAR_FUNC_DEFAULT
from Source.Utility.sprite_data import SpriteData, SpriteRect, AnimationData


def crop_image_rect_left_bot(image: Image, rect: SpriteRect | dict) -> Image:
    _rect: SpriteRect = rect if isinstance(rect, SpriteRect) else SpriteRect.from_dict(rect)
    sx, sy = image.size
    return image.crop((_rect.x, sy - _rect.y - _rect.height, _rect.x + _rect.width, sy - _rect.y))


def crop_image_rect_left_top(image: Image, rect: SpriteRect | dict) -> Image:
    _rect: SpriteRect = rect if isinstance(rect, SpriteRect) else SpriteRect.from_dict(rect)
    return image.crop((_rect.x, _rect.y, _rect.width + _rect.x, _rect.height + _rect.y))


def resize_image(image: Image, scale_factor: int | float) -> Image:
    return image.resize((int(image.size[0] * scale_factor), int(image.size[1] * scale_factor)), Resampling.NEAREST)


def resize_list_images(images: list[Image], scale_factor: int) -> list[Image]:
    return [resize_image(image, scale_factor) for image in images]


def apply_simple_affine_transform(image: Image, matrix: tuple[int, int, int, int]) -> Image:
    """
    Apply simple affine transform to an image: 0/90/180/270 degrees rotation or mirroring
    """
    e00, e10, e01, e11 = matrix

    if e00 + e10 < 0:
        image = ImageOps.mirror(image)

    if e01 + e11 < 0:
        image = ImageOps.flip(image)

    if e10 or e01:
        image = image.rotate(-90)
        image = ImageOps.flip(image)

    return image


def split_name_count(name: str) -> tuple[str, int]:
    name = str(name)
    count = re.search(r"\d+$", name)

    if not count:
        return name, -1

    num = count.group()
    return name[:count.start()] or "_", int(num)


# Note: pivots for sprites of animation are on the same relative pixel for the whole animation
def get_rects_by_sprite_list(sprites_list: list[SpriteData]) -> list[SpriteRect]:
    if not sprites_list:
        return []

    relative_pivots = []
    for sprite in sprites_list:
        pivot = {
            "x": round(sprite.rect.width * sprite.pivot.x),
            "y": round(sprite.rect.height * sprite.pivot.y),
        }
        pivot.update({
            "-x": sprite.rect.width - pivot["x"],
            "-y": sprite.rect.height - pivot["y"]
        })
        relative_pivots.append(pivot)

    max_pivot = {k: max(p[k] for p in relative_pivots) for k in relative_pivots[0].keys()}

    sprite_rects = []
    for sprite, pivot in zip(sprites_list, relative_pivots):
        sprite_rects.append(SpriteRect(
            x := pivot["x"] - max_pivot["x"],
            y := pivot["-y"] - max_pivot["-y"],
            sprite.rect.width + max_pivot["-x"] - pivot["-x"] - x,
            sprite.rect.height + max_pivot["y"] - pivot["y"] - y,
        ))

    return sprite_rects


def get_adjusted_sprites_to_rect(image_rect: Iterable[tuple[Image, SpriteRect]]) -> list[Image]:
    return [crop_image_rect_left_top(img, rect) for img, rect in image_rect]


def get_anim_sprites_ready(anim: AnimationData) -> list[Image]:
    return get_adjusted_sprites_to_rect((img, rect) for img, rect, sprite_name in anim.get_sprites_iter())


def get_tint(tint_dec_int: int) -> tuple[int, int, int]:
    return (
        (tint_dec_int >> 16) & 0xff,
        (tint_dec_int >> 8) & 0xff,
        tint_dec_int & 0xff
    )


def apply_tint(image: Image, tint_color: tuple[int, int, int],
               func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT) -> Image:
    img = image.convert('RGBA')

    luts = [
        [i * tint_color[ch] // 255 for i in range(256)]
        for ch in range(3)
    ]

    rgba = list(img.split())

    n = 3
    mode = 'RGBA'
    for i in range(n):
        rgba[i] = rgba[i].point(luts[i])
        func_progress_bar_set_percent(i + 1, n + 1, mode[i])

    out = PILImage.merge('RGBA', rgba)
    func_progress_bar_set_percent(n + 1, n + 1, "Created new image")

    return out


PILImage.MAX_IMAGE_PIXELS = 2766929920


def create_tint_image(image_path: Path, save_folder: Path, tint_color: tuple[int, int, int],
                      func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT) -> Path:
    with PILImage.open(image_path) as image:
        img = apply_tint(image, tint_color, func_progress_bar_set_percent)

    img.save(save_folder / image_path.name)
    img.transpose(Transpose.ROTATE_180).save(save_folder / f"{image_path.stem}_inv{image_path.suffix}")

    return save_folder


def make_image_black(image: Image, threshold: int = 10) -> Image:
    lut = [255 if i > threshold else 0 for i in range(256)]

    img = image.convert('RGBA')
    alpha = img.getchannel('A').point(lut)
    img.paste((0, 0, 0), (0, 0, *img.size), alpha)
    img.putalpha(alpha)
    return img


def get_wrapped_text(
        text: str,
        font_path: Path,
        text_size: tuple[int, int],
        min_max_font_size: tuple[int, int],
) -> ImageText:
    text_width, text_height = text_size
    min_size, max_size = min_max_font_size
    font = ImageFont.truetype(font_path, max_size)

    image_text = ImageText.Text(text, font)
    image_text.wrap(text_width, text_height, scaling=("shrink", min_size))

    # bug workaround until fixed https://github.com/python-pillow/Pillow/pull/10025
    if image_text.font.size == max_size:
        wrap = ImageText._Wrap(image_text, text_width, text_height, image_text.font)
        image_text.text = "\n".join(wrap.lines)

    return image_text


if __name__ == "__main__":
    pass
    # (255, 170, 255) (136,136, 238)
