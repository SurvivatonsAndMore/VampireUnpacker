import re
from pathlib import Path
from typing import Any


def delete_file(path: Path):
    if path.exists():
        path.unlink()


def clear_file(save_path: Path):
    with open(save_path, "w+", encoding="UTF-8") as f:
        f.write("")


def write_in_file_end(save_path: Path, lines: list[str]):
    with open(save_path, "a+", encoding="UTF-8") as f:
        f.writelines(lines)


def normalize_str(s: Path | str) -> str:
    s = Path(str(s))
    name = s.name
    try:
        index = name.index('.')
    except ValueError:
        index = None
    s = name[:index].lower().replace(",", "_")
    return str(int(s) if s.isnumeric() else s)


_SINGLE_LINE_COMMENT = re.compile(r"\s*//.*\n")
_MULTI_LINE_COMMENT = re.compile(r"(?s)/\*.*?\*/")


def clean_comments_json(string: str) -> str:
    # comments: //
    string = _SINGLE_LINE_COMMENT.sub("\n", string)
    # comments: /* */
    string = _MULTI_LINE_COMMENT.sub("", string)
    return string


_BRACES_COMMA = re.compile(r",([ \t\r\n]+)}")
_BRACKETS_COMMA = re.compile(r",([ \t\r\n]+)]")


def clean_commas_json(string: str) -> str:
    # extra commas
    string = _BRACES_COMMA.sub(r"\1}", string)
    string = _BRACKETS_COMMA.sub(r"\1]", string)
    return string


_ACF_VALUE_COLON = re.compile(r"\"([ \t\r\n]+){")
_ACF_OBJECT_COLON = re.compile(r"\"\t\t\"")
_ACF_VALUE_COMMA = re.compile(r"\"(\n[ \t\r\n]+)\"")
_ACF_OBJECT_COMMA = re.compile(r"}(\n[ \t\r\n]+)\"")


def acf_to_json(string: str) -> str:
    string = string.replace('"AppState"\n', "")
    # add : after key for object
    string = _ACF_VALUE_COLON.sub(r'":\1{', string)
    # add : after key for value
    string = _ACF_OBJECT_COLON.sub("\":\t\t\"", string)
    # add , after value
    string = _ACF_VALUE_COMMA.sub(r'",\1"', string)
    # add , after object
    string = _ACF_OBJECT_COMMA.sub(r'},\1"', string)
    return string


def clean_all_json(string: str) -> str:
    string = clean_comments_json(string)
    return clean_commas_json(string)

_UNDERSCORES_OR_DASHES = re.compile(r"([_\-])+")

def to_pascalcase(s):
    return _UNDERSCORES_OR_DASHES.sub(" ", s).title().replace(" ", "").replace("*", "")


def _find_main_py_file(file_name: str = "unpacker.py") -> Path | None:
    this_folder = Path(__file__).parent

    for _ in range(4):
        try:
            return next(this_folder.glob(file_name))
        except StopIteration:
            this_folder = this_folder.parent

    print(f"!!! Not found {file_name}")
    return None


def get_parent_path_to(path: Path, folder: str) -> Path | None:
    path = path.absolute()
    try:
        idx = path.parts.index(folder)
    except ValueError:
        return None

    return path.parents[len(path.parents) - idx - 1]


def deep_remove_dict_keys(data: dict | list, remove_keys: set[Any]) -> dict | list:
    if isinstance(data, dict):
        return {k: deep_remove_dict_keys(v, remove_keys) for k, v in data.items() if k not in remove_keys}
    elif isinstance(data, list):
        return [deep_remove_dict_keys(v, remove_keys) for v in data]
    return data
