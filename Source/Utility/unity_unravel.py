from itertools import cycle

from Source.Data.meta_data import MetaDataHandler, MetaData, ExactMetaData
from Source.Data.unity_data import UnityDataHandler
from Source.Utility.constants import NOT_UNITY_DATA_CLASS_IDS
from Source.Utility.multirun import map_multiprocess, starmap_multiprocess
from Source.Utility.unity_parser import UnityEntry, UnityDoc, UnityReference, UnityLocalizedReference


def _get_data(_data) -> set[UnityReference]:
    if isinstance(_data, UnityReference):
        if _data.is_valid():
            return {_data}
    elif isinstance(_data, UnityLocalizedReference):
        return set()
    elif isinstance(_data, UnityEntry):
        return _get_data(_data.data)
    elif isinstance(_data, UnityDoc):
        return {obj for entry in _data.entries for obj in _get_data(entry)}
    elif isinstance(_data, dict):
        return {obj for k, v in _data.items() for obj in _get_data(v)}
    elif isinstance(_data, list):
        return {obj for v in _data for obj in _get_data(v)}

    return set()


def _make_data(_data, guid_docs: dict[str, UnityDoc | MetaData]):
    if isinstance(_data, UnityReference):
        if _data.is_valid():
            res_doc = guid_docs.get(_data.guid) or _data.mark_not_found()
            if isinstance(res_doc, MetaData):
                return ExactMetaData.from_meta_data(res_doc, _data.fileID)
            return res_doc
    elif isinstance(_data, UnityLocalizedReference):
        return _data
    elif isinstance(_data, UnityEntry):
        return _data.with_data(_make_data(_data.data, guid_docs))
    elif isinstance(_data, UnityDoc):
        return UnityDoc([_make_data(entry, guid_docs) for entry in _data.entries], guid=_data.guid)
    elif isinstance(_data, dict):
        return {
            k: _make_data(v, guid_docs)
            for k, v in _data.items()
        }
    elif isinstance(_data, list):
        return [_make_data(v, guid_docs) for v in _data]

    return _data


def _unity_unravel_entry(entry: UnityEntry, guid_docs: dict[str, UnityDoc | MetaData]) -> UnityEntry:
    return entry.with_data(_make_data(entry.data, guid_docs))


def unity_unravel_doc(unity_doc: UnityDoc, depth: int = 1, is_load_sprites: bool = True, verbose: int = 1) -> UnityDoc:
    _unity_doc = unity_doc

    guid_docs: dict[str, UnityDoc | MetaData] = {}

    for d in range(depth):
        unity_refs = {
            guid
            for g_list in map_multiprocess(_get_data, [e.data for e in _unity_doc.entries])
            for guid in g_list
        }

        assets = {ref.guid for ref in unity_refs if ref.classID not in NOT_UNITY_DATA_CLASS_IDS}
        sprites = {ref.guid for ref in unity_refs if ref.classID in NOT_UNITY_DATA_CLASS_IDS}

        # print([(ref, MetaDataHandler.get_path_by_guid_no_meta(ref.guid))
        #        for ref in unity_refs if ref.classID not in NOT_UNITY_DATA_CLASS_IDS])

        if verbose > 0:
            print(f"Unraveling UnityDoc. Depth: {d} (Assets to parse: {len(assets)}, Sprites to parse: {len(sprites)})")

        docs = UnityDataHandler.get_data_dict_by_guid_set(assets)
        guid_docs.update(docs)
        if is_load_sprites:
            metas = MetaDataHandler.get_meta_dict_by_guid_set(sprites)
            guid_docs.update(metas)
        else:
            guid_docs.update(dict.fromkeys(sprites))

        args = zip(_unity_doc.entries, cycle((guid_docs,)))

        _unity_doc.entries = starmap_multiprocess(_unity_unravel_entry, args)

    return _unity_doc


if __name__ == "__main__":
    from Source.Config.config import Game

    MetaDataHandler.load(Game.VS)

    db_name = "DlcCatalog"
    print(db_name)

    path = MetaDataHandler.get_path_by_name_no_meta(db_name)
    doc = UnityDoc.yaml_parse_file_smart(path)
    udoc = unity_unravel_doc(doc, depth=2, is_load_sprites=False)

    print(udoc)
