from io import StringIO
from typing import TextIO

from Source.Utility.constants import PROGRAM_FOLDER
from Source.Utility.utility import clear_file


class Logger(StringIO):
    log_path = PROGRAM_FOLDER / "unpacker.log"

    def __init__(self, stream: TextIO | None = None):
        super().__init__()
        self.stream = stream
        clear_file(self.log_path)

    def log(self):
        return open(self.log_path, "a", encoding="UTF-8")

    def write(self, __s):
        if self.stream is not None:
            self.stream.write(__s)
        if "\r" not in __s:
            with self.log() as l:
                l.write(__s)

    def flush(self):
        if self.stream is not None:
            self.stream.flush()
        with self.log() as l:
            l.flush()
