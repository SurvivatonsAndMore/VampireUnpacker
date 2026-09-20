from pathlib import Path

from Source.Data.meta_data import MetaDataHandler
from Source.Utility.multirun import starmap_multiprocess
from Source.Utility.special_classes import Objectless
from Source.Utility.unity_parser import UnityDoc


def _get_doc_with_guid(guid: str, path: Path):
    return UnityDoc.yaml_parse_file_smart(path).set_guid(guid)


class UnityDataHandler(Objectless):
    loaded_data: dict[str, UnityDoc] = {}

    @classmethod
    def get_data_dict_by_guid_set(cls, guids: set[str]) -> dict[str, UnityDoc]:
        not_loaded_set = {guid for guid in guids if guid not in cls.loaded_data}

        if not_loaded_set:
            guid_paths = [(guid, MetaDataHandler.get_path_by_guid_no_meta(guid)) for guid in guids]
            guid_paths_not_none = (arg for arg in guid_paths if arg[-1] is not None)
            # print(guid_paths)
            docs = starmap_multiprocess(_get_doc_with_guid, guid_paths_not_none)
            cls.loaded_data.update({
                doc.guid: doc
                for doc in docs
            })
            # cls.loaded_data.update({
            #     guid: None
            #     for guid, path in guid_paths
            #     if path is None
            # })

        return {
            guid: cls.loaded_data[guid]
            for guid in guids
            if guid in cls.loaded_data
        }

    @classmethod
    def get_data_set_by_guid_set(cls, guids: set[str]) -> set[UnityDoc]:
        return set(cls.get_data_dict_by_guid_set(guids).values())
