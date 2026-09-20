import itertools
import json
import sys
from enum import Enum
from itertools import cycle
from pathlib import Path
from typing import Any

from Source.Config.config import Game
from Source.Data.meta_data import MetaDataHandler, to_current_game_path
from Source.Translations.language_vc import LangHandlerVC
from Source.Utility.constants import DATA_FOLDER, PROGRESS_BAR_FUNC_TYPE, \
    PROGRESS_BAR_FUNC_DEFAULT
from Source.Utility.multirun import map_multiprocess, starmap_multithread
from Source.Utility.unity_parser import UnityDoc, UnityReference, UnityLocalizedReference, UnityEntry
from Source.Utility.unity_unravel import unity_unravel_doc
from Source.Utility.utility import deep_remove_dict_keys


class DataTypeVC(Enum):
    ENEMY = "EnemyDatabase"
    DECK = "AllDecks"  # Not full list of decks
    CARD = "CardDatabase"
    POWER_UP = "PowerUpDatabase"
    RELIC = "RelicDatabase"
    DUNGEON = "AllDungeons"

    TOWN_BUILDING = "TownBuildingDatabase"

    GLOBAL_CONFIG = "GlobalConfig"
    ACHIEVEMENT_CONFIG = "AchievementConfigDatabase"
    GUARDIAN_COFFIN = "GuardianEncounterDatabase"
    REWARD_CONFIG = "RewardConfig_Default"
    LEVEL_CONFIG = "PlayerLevelConfig"
    PLAYER_CONFIG = "PlayerConfig"

    PASSIVE_EVENT = "PassiveEventDatabase"
    EVENT_DETAILS = "EventDetailsDatabase"
    # ENCOUNTER_TEMPLATE_DATABASE = "EncounterTemplateDatabase"  #
    # ENCOUNTER_DATABASE = "EncounterDatabase"  #

    # No database file
    GEM_FREQUENCY = "GemFrequency"
    GEM_FREQUENCY_GROUP = "GemFrequencyGroup"
    DUNGEON_GEN_CONFIG = "DungeonGenConfig"
    FLOOR_LAYER_CONFIG = "FloorLayerConfig"
    ROOM_SPRING_LAYER = "RoomSpringLayer"
    PATH_MST_LAYER = "PathMSTLayer"
    EVENT_LAYER = "EventLayer"
    METADATA_LAYER = "MetadataLayer"

    DUNGEON_CHOICES = "DungeonChoices"
    DESTRUCTIBLE_EVENT_CONFIG = "DestructibleEventConfig"

    ### Unused
    _ARCANA_CONFIG = "ArcanaConfigDatabase"
    _CardGD = "CardGroupDatabase"
    _CardTD = "CardTypeDatabase"
    _DungeonED = "DungeonEventDatabase"
    _DungeonTD = "DungeonTagDatabase"
    _EncounterD = "EncounterDatabase"
    _EncounterTD = "EncounterTemplateDatabase"
    _EventDD = "EventDetailsDatabase"
    _FccD = "FccDatabase"
    _GemD = "GemDatabase"
    _GemTD = "GemTagDatabase"
    _MapTileDD = "MapTileDefinitionDatabase"
    _PassiveED = "PassiveEventDatabase"
    _PropDD = "PropDefinitionDatabase"  # '_assetReference'
    _RoomTD = "RoomTemplateDatabase"  # '_assetReference'

    NONE = None
    BASE = 0

    def get_dumper(self) -> "BaseDataDumper".__class__:
        match self:
            case DataTypeVC.ENEMY:
                return EnemyDataDumper
            case _:
                return BaseDataDumper


def get_available_dumpers() -> list[type["BaseDataDumper"]]:
    stack = [BaseDataDumper]
    available_dumpers: list[type["BaseDataDumper"]] = []
    while stack:
        available_dumpers.extend(filter(lambda d: d.data_type != DataTypeVC.BASE, stack))
        stack = [s for subs in
                 map(lambda x: x.__subclasses__(), filter(lambda d: d.data_type == DataTypeVC.BASE, stack)) for s in
                 subs]

    available_dumpers.sort(key=lambda a: a.data_type.value)
    return available_dumpers


def make_meta_file_folder_structure() -> Path:
    save_path = to_current_game_path(DATA_FOLDER)
    save_path.mkdir(parents=True, exist_ok=True)

    metadata = [s.data_type.value for s in get_available_dumpers()]

    with open(save_path / f"_Metadata.json", "w", encoding="UTF-8") as f:
        print(json.dumps(metadata, indent=2, ensure_ascii=False), file=f)
    return save_path


def dump_selected_data(
        selected_types: list[bool] | None = None,
        func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT
) -> Path:
    assert MetaDataHandler.loaded_game == Game.VC, f"Loaded wrong metadata ({MetaDataHandler.loaded_game}). Need {Game.VC}"

    dumpers = get_available_dumpers()
    selected_types = selected_types or [True] * len(dumpers)

    assert len(selected_types) == len(dumpers), \
        f"Length of selected_types ({len(selected_types)}) does not match length of dumpers ({len(dumpers)})"

    dumpers = list(itertools.compress(dumpers, selected_types))
    total = len(dumpers)

    save_path = Path()
    for i, sub in enumerate(dumpers):
        func_progress_bar_set_percent(i, total, sub.data_type.value)
        try:
            print(sub, sub.data_type.value)
            data = sub.dump_data()
            save_path = sub.save_data(data)
        except Exception as e:
            print(e, file=sys.stderr)
            continue
    func_progress_bar_set_percent(total, total)

    return save_path


def _check_data(_data, name):
    return name in _data and (
            isinstance(_data[name], UnityReference)
            and _data[name].is_valid() or isinstance(_data[name], UnityDoc))


class BaseDataDumper:
    data_type: DataTypeVC = DataTypeVC.BASE

    @classmethod
    def dump_data(cls) -> dict[str, Any] | list[Any]:
        raise NotImplementedError("Data dumper not specified or not supported")

    @classmethod
    def get_udoc(cls, depth: int):
        path = MetaDataHandler.get_path_by_name_no_meta(cls.data_type.value)
        doc = UnityDoc.yaml_parse_file_smart(path)
        return unity_unravel_doc(doc, depth=depth, is_load_sprites=False)

    @staticmethod
    def get_m_Name(doc: UnityDoc | UnityReference | None) -> str | None:
        if doc is None:
            return None
        elif isinstance(doc, UnityDoc):
            # return repr(doc)
            return doc.entry.data.get("m_Name")
        elif isinstance(doc, UnityEntry):
            return doc.data.get("m_Name")
        elif isinstance(doc, UnityReference) and doc.is_not_found():
            return f"{UnityReference.__qualname__}(classID={doc.classID}, <Not found>)"
        elif isinstance(doc, UnityReference) and not doc.is_valid():
            return None
        _text = f"{doc} not dereferenced"
        print(_text, file=sys.stderr)
        return _text

    @staticmethod
    def get_loc_text(loc_ref: UnityLocalizedReference) -> str | None:
        if loc_ref is None or not loc_ref.is_valid():
            return None

        return LangHandlerVC.get_by_loc_ref(loc_ref)

    @classmethod
    def get_data_with_m_Name(cls, _data):
        """
        Deep replace Docs and Refs with m_Name
        """
        if isinstance(_data, (UnityDoc, UnityReference)):
            return cls.get_m_Name(_data)
        elif isinstance(_data, dict):
            return {
                k: cls.get_data_with_m_Name(v)
                for k, v in _data.items()
            }
        elif isinstance(_data, list):
            return [cls.get_data_with_m_Name(v) for v in _data]

        return _data

    @classmethod
    def save_data(cls, full_data: dict[str, Any] | list[Any]) -> Path:
        save_path = to_current_game_path(DATA_FOLDER)
        save_path.mkdir(parents=True, exist_ok=True)
        with open(save_path / f"{cls.data_type.value}.json", "w", encoding="UTF-8") as f:
            print(json.dumps(full_data, indent=2, ensure_ascii=False), file=f)
        return save_path

    @classmethod
    def dump_save_data(cls) -> Path:
        data = cls.dump_data()
        return cls.save_data(data)


class EnemyDataDumper(BaseDataDumper):
    data_type = DataTypeVC.ENEMY

    @classmethod
    def format_data(cls, enemy_config: UnityDoc) -> tuple[str, dict]:
        data: dict = enemy_config.entry.data
        name = data['m_Name'].replace('EnemyConfig_', '')

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in [
            'serializationData', '<AssetId>k__BackingField', 'AllowInTemplate',
            'Prefab', '_idleAnimation', '_deathAnimation', '_spriteMaterial', '_spriteMaterialFar',
            'OutlineColor', '_audioData', '_enableSeparateShadow',
        ], keys)

        data_taken = {k: data.get(k) for k in keys}
        data_taken['_dungeonTags'] = [dt.entry.data['_assetId'] for dt in data_taken['_dungeonTags']]
        data_taken['_enemyTypeTags'] = [et.entry.data['_typeName'] for et in data_taken['_enemyTypeTags']]

        return name, data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udoc = cls.get_udoc(2)

        full_data: dict[str, dict] = {}

        for enemy_config in udoc.entry.data['_assetList']:
            name, data_taken = cls.format_data(enemy_config)
            full_data[name] = data_taken

        return full_data


class DeckDataDumper(BaseDataDumper):
    data_type = DataTypeVC.DECK

    @classmethod
    def get_udoc(cls, depth: int):
        assert False, f"Unsupported function. Use {cls.__class__.__name__}.get_udocs(depth)"

    @classmethod
    def get_udocs(cls, depth: int, verbose: int = 0) -> list[UnityDoc]:
        paths = MetaDataHandler.filter_paths(lambda name_path: name_path[0].endswith('deck'))
        docs = map_multiprocess(UnityDoc.yaml_parse_file_smart, (p.with_suffix("") for n, p in paths))
        return starmap_multithread(unity_unravel_doc, zip(docs, cycle((depth,)), cycle((verbose,))))

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udocs = cls.get_udocs(2)
        udocs.sort(key=lambda d: cls.get_m_Name(d))

        full_data: dict[str, list[str]] = {}

        for deck_config in udocs:
            data: dict = deck_config.entry.data
            name = data['deckName']

            if name in full_data:
                name += "_" + data['m_Name']
            full_data[name] = [cls.get_m_Name(card_config['cardConfig']) for card_config in data['cards']]

        return full_data


class CardDataDumper(BaseDataDumper):
    data_type = DataTypeVC.CARD

    @classmethod
    def format_data(cls, card_config: UnityDoc) -> tuple[str, dict]:
        data: dict = card_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in [
            'serializationData',
            'sprites', 'references',
        ], keys)

        data_taken = {k: data.get(k) for k in keys}

        data_taken['cardType'] = cls.get_m_Name(data_taken['cardType'])
        data_taken['cardGroup'] = cls.get_m_Name(data_taken['cardGroup'])

        data_taken['cardName'] = cls.get_loc_text(data_taken['cardName'])
        data_taken['cardDescription'] = cls.get_loc_text(data_taken['cardDescription'])
        data_taken['levelZeroDescription'] = cls.get_loc_text(data_taken['levelZeroDescription'])
        data_taken['_additionalOnPlayDescription'] = cls.get_loc_text(data_taken['_additionalOnPlayDescription'])

        data_taken['_evolutionComponents'] = [cls.get_m_Name(d) for d in data_taken['_evolutionComponents']]
        data_taken['_excludeGemTags'] = [cls.get_m_Name(d) for d in data_taken['_excludeGemTags']]
        data_taken['_excludeGemTagGroups'] = [cls.get_m_Name(d) for d in data_taken['_excludeGemTagGroups']]

        return cls.get_m_Name(card_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udoc = cls.get_udoc(2)

        full_data: dict[str, dict] = {}

        for card_config in udoc.entry.data['_assetList']:
            name, data_taken = cls.format_data(card_config)
            full_data[name] = data_taken

        return full_data


class CoffinGuardianDataDumper(BaseDataDumper):
    data_type = DataTypeVC.GUARDIAN_COFFIN

    @classmethod
    def format_data(cls, guardian_config: UnityDoc) -> tuple[str, dict]:
        data: dict = guardian_config.entry.data
        name = data['_assetId']

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in [
            'serializationData', '_destructiblePropDefinition', '_overriddenCameraSettings', '_edgeEventBumpSFX',
            'unlockedAchievement', 'guardianPulseCurve',
        ], keys)

        data_taken = {k: data.get(k) for k in keys}
        data_taken['_treasureEventDetailsReference'] = data['_treasureEventDetailsReference'].get('_assetId')
        data_taken['_defaultEventDetailsReference'] = data['_defaultEventDetailsReference']["_assetId"]
        name_guardian, config_guardian = EnemyDataDumper.format_data(data_taken['guardian'])
        config_guardian["__name"] = name_guardian
        data_taken['guardian'] = config_guardian
        if isinstance(ach_doc := data.get('unlockedAchievement'), UnityDoc):
            data_taken['unlockedAchievement'] = cls.get_m_Name(ach_doc)

        return name, data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udoc = cls.get_udoc(3)

        full_data: dict[str, dict] = {}

        for guardian_config in udoc.entry.data['_assetList']:
            name, data_taken = cls.format_data(guardian_config)
            full_data[name] = data_taken

        return full_data


class RewardConfigDataDumper(BaseDataDumper):
    data_type = DataTypeVC.REWARD_CONFIG

    @classmethod
    def dump_data(cls) -> list[dict[str, Any]]:
        udoc = cls.get_udoc(2)

        full_data: list[dict[str, Any]] = []

        for reward_config in udoc.entry.data['_levelRanges']:
            data_taken = reward_config
            data_taken['_cards'] = [cls.get_m_Name(card_doc) for card_doc in data_taken['_cards']]
            data_taken['_cardGroups'] = [card_doc.entry.data['_assetId'] for card_doc in data_taken['_cardGroups']]

            full_data.append(data_taken)

        return full_data


class LevelConfigDataDumper(BaseDataDumper):
    data_type = DataTypeVC.LEVEL_CONFIG

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udoc = cls.get_udoc(0)

        full_data = {
            k: v
            for k, v in udoc.entry.data.items()
            if k in ['_baseXpReq', '_levelRanges']
        }

        return full_data


class PlayerConfigDataDumper(BaseDataDumper):
    data_type = DataTypeVC.PLAYER_CONFIG

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udoc = cls.get_udoc(0)

        data = udoc.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in [
            '_playerAudioConfig'
        ], keys)

        full_data = {k: data.get(k) for k in keys}

        return full_data


class AchievementDataDumper(BaseDataDumper):
    data_type = DataTypeVC.ACHIEVEMENT_CONFIG

    @classmethod
    def format_data(cls, ach_config: UnityDoc) -> tuple[str, dict]:
        data: dict = ach_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData',
            '_unlockRewardIcon',
            'references',
        }, keys)

        data_taken = {k: data.get(k) for k in keys}

        data_taken['_dungeonConfig'] = cls.get_m_Name(data_taken.get('_dungeonConfig'))
        data_taken['_fccConfig'] = cls.get_m_Name(data_taken.get('_fccConfig'))
        data_taken['_encounterConfig'] = cls.get_m_Name(data_taken.get('_encounterConfig'))
        data_taken['_powerUpConfig'] = cls.get_m_Name(data_taken.get('_powerUpConfig'))

        data_taken['_achievementName'] = cls.get_loc_text(data_taken['_achievementName'])
        data_taken['_achievementDescription'] = cls.get_loc_text(data_taken['_achievementDescription'])
        data_taken['_platformTrophyDescription'] = cls.get_loc_text(data_taken['_platformTrophyDescription'])
        data_taken['_rewardName'] = cls.get_loc_text(data_taken['_rewardName'])
        data_taken['_rewardDescription'] = cls.get_loc_text(data_taken['_rewardDescription'])
        data_taken['_hiddenString'] = cls.get_loc_text(data_taken['_hiddenString'])
        data_taken['_flavourText'] = cls.get_loc_text(data_taken['_flavourText'])

        data_taken['_achievementsRequired'] = [cls.get_m_Name(d) for d in data_taken.get('_achievementsRequired', [])]

        if '_criteriasToMeet' in data_taken:
            for ci in data_taken['_criteriasToMeet']:
                ci['FccToCheck'] = cls.get_m_Name(ci['FccToCheck'])
        else:
            data_taken['_criteriasToMeet'] = []

        return cls.get_m_Name(ach_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udoc = cls.get_udoc(2)

        full_data: dict[str, dict] = {}

        for ach_config in udoc.entry.data['_assetList']:
            name, data_taken = cls.format_data(ach_config)
            full_data[name] = data_taken

        return full_data


class PowerUpDataDumper(BaseDataDumper):
    data_type = DataTypeVC.POWER_UP

    @classmethod
    def format_data(cls, power_up_config: UnityDoc) -> tuple[str, dict]:
        data: dict = power_up_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'imageSprite',
            'references',
        }, keys)

        data_taken = {k: data.get(k) for k in keys}

        data_taken['itemName'] = cls.get_loc_text(data_taken['itemName'])
        data_taken['description'] = cls.get_loc_text(data_taken['description'])

        return cls.get_m_Name(power_up_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udoc = cls.get_udoc(2)

        full_data: dict[str, dict] = {}

        for power_up_config in udoc.entry.data['_assetList']:
            name, data_taken = cls.format_data(power_up_config)
            full_data[name] = data_taken

        return full_data


class RelicDataDumper(BaseDataDumper):
    data_type = DataTypeVC.RELIC

    @classmethod
    def format_data(cls, relic_config: UnityDoc) -> tuple[str, dict]:
        data: dict = relic_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'imageSprite',
            'IconSprite',
            'references',
        }, keys)

        data_taken = {k: data.get(k) for k in keys}

        data_taken['LocalizedName'] = cls.get_loc_text(data_taken['LocalizedName'])
        data_taken['_localizedDescription'] = cls.get_loc_text(data_taken['_localizedDescription'])

        return cls.get_m_Name(relic_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udoc = cls.get_udoc(2)

        full_data: dict[str, dict] = {}

        for relic_config in udoc.entry.data['_assetList']:
            name, data_taken = cls.format_data(relic_config)
            full_data[name] = data_taken

        return full_data


class DungeonsDataDumper(BaseDataDumper):
    data_type = DataTypeVC.DUNGEON

    @classmethod
    def format_data(cls, dungeon_config: UnityDoc) -> tuple[str, dict]:
        data: dict = dungeon_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references',
            '_dungeonThumbnailSprite', '_soundGroupCreator', '_reverbZonePrefab',
        }, keys)

        data_taken = {k: data.get(k) for k in keys}

        data_taken['GenerationConfig'] = cls.get_m_Name(data_taken.get('GenerationConfig'))  ## ?

        data_taken['_cameraVolumeProfile'] = cls.get_m_Name(data_taken.get('_cameraVolumeProfile'))
        data_taken['_skyboxMaterial'] = cls.get_m_Name(data_taken.get('_skyboxMaterial'))
        data_taken['_traversalBGM'] = cls.get_m_Name(data_taken.get('_traversalBGM'))
        data_taken['_battleBGM'] = cls.get_m_Name(data_taken.get('_battleBGM'))

        data_taken['<DungeonNameLoc>k__BackingField'] = cls.get_loc_text(data_taken['<DungeonNameLoc>k__BackingField'])
        data_taken['<DungeonDescriptionLoc>k__BackingField'] = cls.get_loc_text(
            data_taken['<DungeonDescriptionLoc>k__BackingField'])

        data_taken['_relicsInLevel'] = [cls.get_m_Name(d) for d in data_taken.get('_relicsInLevel', [])]
        data_taken['_coffinsInLevel'] = [cls.get_m_Name(d) for d in data_taken.get('_coffinsInLevel', [])]

        return cls.get_m_Name(dungeon_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udoc = cls.get_udoc(2)

        full_data: dict[str, dict] = {}

        for dungeon_config in udoc.entry.data['_assetList']:
            name, data_taken = cls.format_data(dungeon_config)
            full_data[name] = data_taken

        return full_data


class TownBuildingDataDumper(BaseDataDumper):
    data_type = DataTypeVC.TOWN_BUILDING

    @classmethod
    def format_data(cls, dungeon_config: UnityDoc) -> tuple[str, dict]:
        data: dict = dungeon_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references',

        }, keys)

        data_taken = {k: data.get(k) for k in keys}

        data_taken['_musicOverride'] = cls.get_m_Name(data_taken.get('_musicOverride'))

        data_taken['_townBuildingName'] = cls.get_loc_text(data_taken['_townBuildingName'])
        data_taken['_menuName'] = cls.get_loc_text(data_taken['_menuName'])
        data_taken['_unlockedBuildingDesc'] = cls.get_loc_text(data_taken['_unlockedBuildingDesc'])
        data_taken['_lockedBuildingDesc'] = cls.get_loc_text(data_taken['_lockedBuildingDesc'])

        return cls.get_m_Name(dungeon_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udoc = cls.get_udoc(2)

        full_data: dict[str, dict] = {}

        for dungeon_config in udoc.entry.data['_assetList']:
            name, data_taken = cls.format_data(dungeon_config)
            full_data[name] = data_taken

        return full_data


class GlobalConfigDataDumper(BaseDataDumper):
    data_type = DataTypeVC.GLOBAL_CONFIG

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udoc = cls.get_udoc(2)

        data: dict = udoc.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references',
        }, keys)

        full_data = {
            k: cls.get_data_with_m_Name(data.get(k))
            for k in keys
        }

        return full_data


class PassiveEventDataDumper(BaseDataDumper):
    data_type = DataTypeVC.PASSIVE_EVENT

    @classmethod
    def format_data(cls, event_config: UnityDoc) -> tuple[str, dict]:
        data: dict = event_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references',
        }, keys)

        data_taken = {k: data.get(k) for k in keys}

        data_taken['_destructiblePropDefinition'] = cls.get_m_Name(data_taken['_destructiblePropDefinition'])
        data_taken['PassiveEventView'] = cls.get_m_Name(data_taken['PassiveEventView'])

        data_taken['_defaultEventDetailsReference'] = deep_remove_dict_keys(data_taken['_defaultEventDetailsReference'],
                                                                            {"_editorAssetGuid"})

        return cls.get_m_Name(event_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udoc = cls.get_udoc(2)

        full_data: dict[str, dict] = {}

        for event_config in udoc.entry.data['_assetList']:
            name, data_taken = cls.format_data(event_config)
            full_data[name] = data_taken

        return full_data


class EventDetailsDataDumper(BaseDataDumper):
    data_type = DataTypeVC.EVENT_DETAILS

    @classmethod
    def format_data(cls, event_config: UnityDoc) -> tuple[str, dict]:
        data: dict = event_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references',
            'Icon'
        }, keys)

        data_taken = {k: data.get(k) for k in keys}

        if _check_data(data_taken, '_eventMarkerPrefab'):
            data_taken['_eventMarkerPrefab'] = list(
                filter(None, map(cls.get_m_Name, data_taken['_eventMarkerPrefab'].entries)))
        else:
            data_taken['_eventMarkerPrefab'] = None

        return cls.get_m_Name(event_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udoc = cls.get_udoc(2)

        full_data: dict[str, dict] = {}

        for event_config in udoc.entry.data['_assetList']:
            name, data_taken = cls.format_data(event_config)
            full_data[name] = data_taken

        return full_data


class MultipleDataDumper(BaseDataDumper):
    data_type = DataTypeVC.BASE

    @classmethod
    def get_udoc(cls, depth: int):
        assert False, f"Unsupported function. Use {cls.__class__.__name__}.get_udocs(depth)"

    @classmethod
    def get_udocs(cls, search_prefix: str | set[str], depth: int, verbose: int = 0) -> list[UnityDoc]:
        if isinstance(search_prefix, str):
            search_prefix = {search_prefix}
        search_prefix = {sp.lower() for sp in search_prefix}

        found_paths = set()
        for sp in search_prefix:
            paths = MetaDataHandler.filter_paths(
                lambda name_path: name_path[0].startswith(sp) and not name_path[0].endswith('.meta'))
            found_paths.update((p.with_suffix("") for n, p in paths))

        docs = map_multiprocess(UnityDoc.yaml_parse_file_smart, found_paths)
        return starmap_multithread(unity_unravel_doc, zip(docs, cycle((depth,)), cycle((verbose,))))


class GemFrequencyDataDumper(MultipleDataDumper):
    data_type = DataTypeVC.GEM_FREQUENCY

    @classmethod
    def format_data(cls, gem_config: UnityDoc) -> tuple[str, dict]:
        data: dict = gem_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references',
            '_frequencyColor',
        }, keys)

        data_taken = {k: data.get(k) for k in keys}

        data_taken['_frequencyName'] = cls.get_loc_text(data_taken.get('_frequencyName'))

        return cls.get_m_Name(gem_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udocs = cls.get_udocs('gemfrequency_', 2)
        udocs.sort(key=lambda d: cls.get_m_Name(d))

        full_data: dict[str, dict] = {}

        for gem_config in udocs:
            name, data_taken = cls.format_data(gem_config)
            full_data[name] = data_taken

        return full_data


class GemFrequencyGroupDataDumper(MultipleDataDumper):
    data_type = DataTypeVC.GEM_FREQUENCY_GROUP

    @classmethod
    def format_data(cls, gem_config: UnityDoc) -> tuple[str, dict]:
        data: dict = gem_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references',
            '_frequencyColor',
        }, keys)

        data_taken = {k: data.get(k) for k in keys}

        data_taken['_frequencies'] = cls.get_data_with_m_Name(data_taken['_frequencies'])

        return cls.get_m_Name(gem_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udocs = cls.get_udocs('gemfrequencygroup', 2)
        udocs.sort(key=lambda d: cls.get_m_Name(d))

        full_data: dict[str, dict] = {}

        for gem_config in udocs:
            name, data_taken = cls.format_data(gem_config)
            full_data[name] = data_taken

        return full_data


class DungeonGenConfigDataDumper(MultipleDataDumper):
    data_type = DataTypeVC.DUNGEON_GEN_CONFIG

    @classmethod
    def format_data(cls, gen_config: UnityDoc) -> tuple[str, dict]:
        data: dict = gen_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references',
        }, keys)

        data_taken = {k: data.get(k) for k in keys}

        if '_floors' in data_taken:
            for i in range(len(data_taken['_floors'])):
                data_taken['_floors'][i]['FloorLayer'] = cls.get_m_Name(data_taken['_floors'][i]['FloorLayer'])

                excl = '<Manually Excluded>'
                dfclt = data_taken['_floors'][i]['Difficulty']
                data_taken['_floors'][i]['Difficulty'] = deep_remove_dict_keys(data_taken['_floors'][i]['Difficulty'],
                                                                               {"serializedVersion"})

        data_taken['_endlessModeStatConfig'] = cls.get_m_Name(data_taken.get('_endlessModeStatConfig'))

        return cls.get_m_Name(gen_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udocs = cls.get_udocs('dungeongen', 1)
        udocs.sort(key=lambda d: cls.get_m_Name(d))

        full_data: dict[str, dict] = {}

        for gen_config in udocs:
            name, data_taken = cls.format_data(gen_config)
            full_data[name] = data_taken

        return full_data


class FloorLayerConfigDataDumper(MultipleDataDumper):
    data_type = DataTypeVC.FLOOR_LAYER_CONFIG

    @classmethod
    def format_data(cls, floor_config: UnityDoc) -> tuple[str, dict]:
        data: dict = floor_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references',
            '_stepConfig', '_dungeonEnvironmentPrefab',
        }, keys)

        data_taken = {k: data.get(k) for k in keys}

        if '_floorLayers' in data_taken:
            data_taken['_floorLayers'] = [cls.get_m_Name(d) for d in data_taken['_floorLayers']]

        data_taken['_dungeonTag'] = cls.get_m_Name(data_taken.get('_dungeonTag'))

        return cls.get_m_Name(floor_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udocs = cls.get_udocs('floorlayerconfig', 1)
        udocs.sort(key=lambda d: cls.get_m_Name(d))

        full_data: dict[str, dict] = {}

        for floor_config in udocs:
            name, data_taken = cls.format_data(floor_config)
            full_data[name] = data_taken

        return full_data


class RoomSpringLayerDataDumper(MultipleDataDumper):
    data_type = DataTypeVC.ROOM_SPRING_LAYER

    @classmethod
    def format_data(cls, room_config: UnityDoc) -> tuple[str, dict]:
        data: dict = room_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references'
        }, keys)

        data_taken = {k: data.get(k) for k in keys}

        if _check_data(data_taken, '_rulesOverride'):
            name, rules = cls.rules_override_format_data(data_taken['_rulesOverride'])
            rules["m_Name"] = name
            data_taken['_rulesOverride'] = rules
        else:
            data_taken['_rulesOverride'] = None

        if _check_data(data_taken, '_configOverride'):
            name, config = cls.config_override_format_data(data_taken['_configOverride'])
            config["m_Name"] = name
            data_taken['_configOverride'] = config
        else:
            data_taken['_configOverride'] = None

        return cls.get_m_Name(room_config), data_taken

    @classmethod
    def rules_override_format_data(cls, rules: UnityDoc) -> tuple[str, dict]:
        data: dict = rules.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references'
        }, keys)

        data_taken = {k: data.get(k) for k in keys}

        data_taken['_rules'] = cls.get_data_with_m_Name(data_taken['_rules'])

        return cls.get_m_Name(rules), data_taken

    @classmethod
    def config_override_format_data(cls, config: UnityDoc) -> tuple[str, dict]:
        data: dict = config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references'
        }, keys)

        data_taken = {k: data.get(k) for k in keys}

        return cls.get_m_Name(config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udocs = cls.get_udocs('roomspringlayer', 2)
        udocs.sort(key=lambda d: cls.get_m_Name(d))

        full_data: dict[str, dict] = {}

        for room_config in udocs:
            name, data_taken = cls.format_data(room_config)
            full_data[name] = data_taken

        return full_data


class PathMSTLayerDataDumper(MultipleDataDumper):
    data_type = DataTypeVC.PATH_MST_LAYER

    @classmethod
    def format_data(cls, path_config: UnityDoc) -> tuple[str, dict]:
        data: dict = path_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references',
        }, keys)

        data_taken = {k: data.get(k) for k in keys}

        return cls.get_m_Name(path_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udocs = cls.get_udocs('pathmstlayer', 1)
        udocs.sort(key=lambda d: cls.get_m_Name(d))

        full_data: dict[str, dict] = {}

        for path_config in udocs:
            name, data_taken = cls.format_data(path_config)
            full_data[name] = data_taken

        return full_data


class MetadataLayerDataDumper(MultipleDataDumper):
    data_type = DataTypeVC.METADATA_LAYER

    @classmethod
    def format_data(cls, meta_config: UnityDoc) -> tuple[str, dict]:
        data: dict = meta_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references',
        }, keys)

        data_taken = cls.get_data_with_m_Name({k: data.get(k) for k in keys})

        return cls.get_m_Name(meta_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udocs = cls.get_udocs({'metadatalayer', 'metalayer'}, 1)
        udocs.sort(key=lambda d: cls.get_m_Name(d))

        full_data: dict[str, dict] = {}

        for meta_config in udocs:
            name, data_taken = cls.format_data(meta_config)
            full_data[name] = data_taken

        return full_data


class EventLayerDataDumper(MultipleDataDumper):
    data_type = DataTypeVC.EVENT_LAYER

    @classmethod
    def format_data(cls, event_config: UnityDoc) -> tuple[str, dict]:
        data: dict = event_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references',
        }, keys)

        data_taken = cls.get_data_with_m_Name({k: data.get(k) for k in keys})
        data_taken = deep_remove_dict_keys(data_taken, {"_editorAssetGuid"})

        return cls.get_m_Name(event_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udocs = cls.get_udocs('eventlayer', 1)
        udocs.sort(key=lambda d: cls.get_m_Name(d).replace("_", ""))

        full_data: dict[str, dict] = {}

        for event_config in udocs:
            name, data_taken = cls.format_data(event_config)
            full_data[name] = data_taken

        return full_data


class DungeonChoicesDataDumper(MultipleDataDumper):
    data_type = DataTypeVC.DUNGEON_CHOICES

    @classmethod
    def format_data(cls, choice_config: UnityDoc) -> tuple[str, dict]:
        data: dict = choice_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references',
        }, keys)

        data_taken = {k: data.get(k) for k in keys}
        data_taken = deep_remove_dict_keys(data_taken, {"_editorAssetGuid"})

        return cls.get_m_Name(choice_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udocs = cls.get_udocs('dungeonchoices', 1)
        udocs.sort(key=lambda d: cls.get_m_Name(d).replace("_", ""))

        full_data: dict[str, dict] = {}

        for choice_config in udocs:
            name, data_taken = cls.format_data(choice_config)
            full_data[name] = data_taken

        return full_data


class DestructibleEventConfigDataDumper(MultipleDataDumper):
    data_type = DataTypeVC.DESTRUCTIBLE_EVENT_CONFIG

    @classmethod
    def format_data(cls, event_config: UnityDoc) -> tuple[str, dict]:
        data: dict = event_config.entry.data

        keys = data.keys()
        keys = filter(lambda k: not k.startswith("m_"), keys)
        keys = filter(lambda k: k not in {
            'serializationData', 'references',
        }, keys)

        data_taken = {k: data.get(k) for k in keys}
        data_taken = deep_remove_dict_keys(data_taken, {"_editorAssetGuid"})

        data_taken['_destructiblePropDefinition'] = cls.get_m_Name(data_taken.get('_destructiblePropDefinition'))

        return cls.get_m_Name(event_config), data_taken

    @classmethod
    def dump_data(cls) -> dict[str, Any]:
        udocs = cls.get_udocs('destructibleeventconfig', 1)
        udocs.sort(key=lambda d: cls.get_m_Name(d).replace("_", ""))

        full_data: dict[str, dict] = {}

        for event_config in udocs:
            name, data_taken = cls.format_data(event_config)
            full_data[name] = data_taken

        return full_data


if __name__ == "__main__":
    MetaDataHandler.load(Game.VC)
    # CardDataDumper.dump_data()
    EventDetailsDataDumper.dump_save_data()
    # dump_selected_data()
    # make_meta_file_folder_structure()
