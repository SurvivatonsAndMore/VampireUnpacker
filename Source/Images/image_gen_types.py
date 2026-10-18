from __future__ import annotations

from enum import Enum


class GenType(Enum):
    IMAGE = 0
    IMAGE_FRAME = 1

    ARCANA_PICTURE = 10

    CHARACTER_SKINS = 20
    CHARACTER_SPECIAL_SELECT = 21

    STAGE_WITH_NAME = 30

    TEXT_STROKE_WIDTH = 31

    ANIM = 100
    ANIM_SPECIAL = 101
    ANIM_DEATH = 102

    @classmethod
    def get_types(cls) -> set[GenType]:
        return {*cls}

    @classmethod
    def get_int_types(cls) -> set[GenType]:
        return {cls.IMAGE, cls.TEXT_STROKE_WIDTH}

    def get_input_value(self, value):
        match self:
            case GenType.IMAGE:
                return int(value)
            case GenType.TEXT_STROKE_WIDTH:
                return float(value)
            case _:
                return value

    def get_tip(self) -> str:
        match self:
            case GenType.IMAGE:
                return "Scale factor"
            case GenType.IMAGE_FRAME:
                return "Generate frame variants"

            case GenType.ANIM:
                return "Generate animations"
            case GenType.ANIM_DEATH:
                return "Generate death animations"
            case GenType.ANIM_SPECIAL:
                return "Generate special animations"

            case GenType.ARCANA_PICTURE:
                return "Generate arcana pictures"

            case GenType.CHARACTER_SPECIAL_SELECT:
                return "Generate special select variants"
            case GenType.CHARACTER_SKINS:
                return "Generate character skins"

            case GenType.STAGE_WITH_NAME:
                return "Generate with stage name"
            case GenType.TEXT_STROKE_WIDTH:
                return "Text stroke width"
        return None

    def is_anim(self):
        match self:
            case GenType.ANIM | GenType.ANIM_DEATH | GenType.ANIM_SPECIAL:
                return True
        return False

def has_requested_anim(requested_gens: dict[GenType, int | float | bool]):
    return any(val for gen, val in requested_gens.items() if gen.is_anim())