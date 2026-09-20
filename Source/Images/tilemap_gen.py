import itertools
from pathlib import Path

from PIL.Image import Image, new as image_new

from Source.Config.config import Config
from Source.Data.meta_data import MetaData, MetaDataHandler, to_current_game_path
from Source.Utility.constants import IMAGES_FOLDER, GENERATED, TILEMAPS, PROGRESS_BAR_FUNC_TYPE, \
    PROGRESS_BAR_FUNC_DEFAULT
from Source.Utility.image_functions import apply_simple_affine_transform, crop_image_rect_left_bot
from Source.Utility.multirun import starmap_multithread
from Source.Utility.special_classes import Objectless
from Source.Utility.sprite_data import SpriteData, SpriteRect
from Source.Utility.timer import Timeit
from Source.Utility.unity_parser import UnityDoc, UnityEntry
from Source.Utility.utility import write_in_file_end, delete_file


class Tilemap:
    def __init__(self, doc: UnityEntry):
        self.m_Size = doc.get("m_Size")
        self.m_TileMatrixArray = doc.get("m_TileMatrixArray")
        self.m_TileSpriteArray = doc.get("m_TileSpriteArray")
        self.m_Tiles = doc.get("m_Tiles")

    def extend_tilemap(self, other: "Tilemap"):
        self.m_Tiles.extend(other.m_Tiles)

    @staticmethod
    def get_size_tile() -> tuple[int, int]:
        return 32, 32


class TilemapDataHandler(Objectless):
    loaded_prefabs: dict[Path, list[Tilemap | None]] = dict()
    layer_counts: dict[Path, int] = dict()


def __resize_sprite_for_tile(image: Image, sprite_data: SpriteData, size_tile: tuple[int, int]) -> Image:
    shift_x = int(sprite_data.rect.width * sprite_data.pivot.x)
    shift_y = int(sprite_data.rect.height * sprite_data.pivot.y)

    rect = SpriteRect(shift_x, shift_y, size_tile[0], size_tile[1])
    return crop_image_rect_left_bot(image, rect)


def __load_unity_document(path: Path) -> list[Tilemap | None]:
    doc = UnityDoc.yaml_parse_file_smart(path, lambda x: "Tilemap:" in x)
    tilemaps = [Tilemap(tilemap) for tilemap in doc.entries]
    return tilemaps


def __create_tilemap_image(tilemap: Tilemap, new_image: Image, data_by_guid: dict[str: MetaData],
                           save_path: Path) -> Image:
    size_tile_x, size_tile_y = Tilemap.get_size_tile()

    tile_sprite_array = [(int(x["m_Data"]["fileID"]), x["m_Data"]["guid"]) for x in tilemap.m_TileSpriteArray]
    tile_matrix_array = [{k: float(v) for k, v in x["m_Data"].items()} if int(x["m_RefCount"]) > 0 else {} for x in
                         tilemap.m_TileMatrixArray]
    tiles = ({
        "pos": {k: int(v) for k, v in tile["first"].items()},
        "tile_index": int(tile["second"]["m_TileIndex"]),
        "matrix_index": int(tile["second"]["m_TileMatrixIndex"])
    } for tile in tilemap.m_Tiles)

    log_list = []
    for tile in tiles:
        tile_inner_id, texture_guid = tile_sprite_array[tile["tile_index"]]

        data: MetaData = data_by_guid.get(texture_guid)
        sprite_data = data.data_id.get(tile_inner_id)
        sprite = sprite_data.sprite

        if not sprite:
            line = f"Sprite error: {texture_guid=} {tile_inner_id=}\n"
            log_list.append(line)
            continue

        sprite = __resize_sprite_for_tile(sprite, sprite_data, (size_tile_x, size_tile_y))

        matrix = tile_matrix_array[tile["matrix_index"]]
        if matrix["e00"] != 1 or matrix["e11"] != 1:
            affine = (matrix["e00"], matrix["e10"], matrix["e01"], matrix["e11"])
            sprite = apply_simple_affine_transform(sprite, affine)

        new_image.alpha_composite(sprite, (tile['pos']['x'] * size_tile_x, abs(tile['pos']['y']) * size_tile_y))

    if log_list:
        write_in_file_end(save_path / "errors.log", log_list)

    return new_image


def __save_image(image: Image, path: Path) -> None:
    # image.save(path, compression_level=3)
    image.save(path)


def get_tilemap_layers_count(path: Path) -> int:
    if path in TilemapDataHandler.layer_counts:
        return TilemapDataHandler.layer_counts[path]

    _text = path.read_text(encoding="UTF-8")
    count_layers = _text.count("Tilemap:")

    TilemapDataHandler.layer_counts[path] = count_layers
    return count_layers


def create_tilemap(
        path: Path,
        exclude_layers: set[int],
        func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT
) -> Path | None:
    tilemap_name = path.name
    save_file = path.stem
    save_folder = to_current_game_path(IMAGES_FOLDER) / GENERATED / TILEMAPS / save_file

    count_layers = get_tilemap_layers_count(path)

    print(f"Excluded layers: {exclude_layers}")

    if path not in TilemapDataHandler.loaded_prefabs:
        print(f"Started {tilemap_name} parsing")
        timeit = Timeit()
        TilemapDataHandler.loaded_prefabs[path] = __load_unity_document(path)
        print(f"Finished {tilemap_name} parsing ({timeit:.2f} sec)")
    else:
        print(f"Already parsed {tilemap_name}")

    tilemaps = TilemapDataHandler.loaded_prefabs[path]

    guid_set = {sprite["m_Data"]["guid"] for tilemap in tilemaps for sprite in tilemap.m_TileSpriteArray}

    print(f"Required guids: {guid_set}")

    meta_data = MetaDataHandler.get_meta_dict_by_guid_set(guid_set)

    for md in meta_data.values():
        md.init_sprites()

    save_folder.mkdir(parents=True, exist_ok=True)

    print(f"Started generating tilemap layers for {tilemap_name}")
    delete_file(save_folder / "errors.log")
    timeit = Timeit()

    size_map_x, size_map_y = 0, 0
    for tilemap in tilemaps:
        _size = tilemap.m_Size
        size_map_x = max(size_map_x, int(_size['x']))
        size_map_y = max(size_map_y, int(_size['y']))

    size_tile_x, size_tile_y = Tilemap.get_size_tile()

    def get_transparent_image():
        return image_new(mode="RGBA", size=(size_map_x * size_tile_x, size_map_y * size_tile_y))

    total_map_size = size_map_x * size_map_y
    print(f"Tilemap size: x={size_map_x}, y={size_map_y}; total={total_map_size}")

    args_create_tilemap = (
        (tilemap, get_transparent_image(), meta_data, save_folder / f"{save_file}-Layer-{i}.png")
        for i, tilemap in enumerate(tilemaps)
    )

    tilemap_layers = itertools.starmap(__create_tilemap_image, args_create_tilemap)

    print(f"Finished generation for tilemap layers {tilemap_name} ({timeit:.2f} sec)")

    print(f"Started composing layers for {tilemap_name}")
    timeit = Timeit()

    im_map = get_transparent_image()

    for i, layer in enumerate(tilemap_layers):
        func_progress_bar_set_percent(i, count_layers - 1)

        to_save = [(layer, save_folder / f"{save_file}-Layer-{i}.png")]

        if i not in exclude_layers:
            im_map.alpha_composite(layer)
            to_save.append((im_map, save_folder / f"{save_file}-{i}.png"))

        starmap_multithread(__save_image, to_save)

    print(f"Finished generation for tilemap {tilemap_name} ({timeit:.2f} sec)")

    return save_folder


if __name__ == "__main__":
    def __test():
        name = "Collab1_Tileset1_V6"
        tile_id = 21303880

        from Source.Data.meta_data import MetaDataHandler
        meta = MetaDataHandler.get_meta_by_name(name, is_multiprocess=False)
        meta.init_sprites()

        meta = meta.data_id

        size_tile = (32,) * 2
        sprite_data = meta.get(tile_id)
        sprite = sprite_data.sprite
        if not sprite:
            return

        transform_list = ((1, 1), (1, -1), (-1, 1), (-1, -1))

        save_folder = Path("./Generated/_Tilemaps/_Test")
        save_folder.mkdir(parents=True, exist_ok=True)
        sprite.save(save_folder.joinpath(f"{tile_id}.png"))

        for i, (x1, x2) in enumerate(transform_list):
            aff1 = (x1, 0, 0, x2)
            aff2 = (0, x1, x2, 0)

            sprite1 = sprite.copy()
            sprite2 = sprite.copy()

            sprite1 = __resize_sprite_for_tile(sprite1, sprite_data, size_tile)
            sprite2 = __resize_sprite_for_tile(sprite2, sprite_data, size_tile)

            sprite1 = apply_simple_affine_transform(sprite1, aff1)
            sprite2 = apply_simple_affine_transform(sprite2, aff2)

            sprite1.save(save_folder.joinpath(f"{tile_id}-1_{i}.png"))
            sprite2.save(save_folder.joinpath(f"{tile_id}-2_{i}.png"))


    # __test()

    def __profile():
        from tkinter import filedialog as fd
        from Source.Config.config import Game
        from Source.Utility.constants import GAME_OBJECT
        MetaDataHandler.load(Game.VS)

        full_path = fd.askopenfilename(
            title='Select prefab file of tilemap',
            initialdir=Config.get_assets_dir(Game.VS) / GAME_OBJECT,
            filetypes=[('Prefab', '*.prefab')]
        )
        if not full_path:
            return
        full_path = Path(full_path)

        import cProfile
        print("Started")
        with cProfile.Profile() as pr:
            create_tilemap(full_path, set())
            # pr.print_stats('time')
            pr.dump_stats('./tilemap.prof')

    # __profile()
