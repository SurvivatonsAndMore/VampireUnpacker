from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from Source.Data.data_sur import DataType
from Source.Images.image_gen_types import GenType


class CheckBoxes(tk.Toplevel):

    @staticmethod
    def execute[T](list_to_boxes: list[T], title="", label: str | list[str] = "", parent=None, width: int = 300) -> \
    list[
        bool] | None:
        cbs = CheckBoxes(list_to_boxes, title=title, label=label, parent=parent, width=width)
        cbs.wait_window()
        return cbs.return_data

    def __init__[T](self, list_to_boxes: list[T], title="", label: str | list[str] = "", parent=None, width: int = 300):
        super().__init__(parent)

        self.return_data = None
        self.parent = parent
        self.title(title)
        self.minsize(width, 200)

        if isinstance(label, str):
            ttk.Label(self, text=label).pack()
        else:
            for lab in label:
                ttk.Label(self, text=lab).pack()

        self.global_state = tk.BooleanVar()

        cb = ttk.Checkbutton(self, text="Select/Deselect all",
                             variable=self.global_state,
                             command=self.set_all)
        cb.pack()

        self.states = []

        for i, val in enumerate(list_to_boxes):
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(self, text=val, variable=var)
            cb.pack()
            self.states.append(var)

        b_ok = ttk.Button(self, text="Select", command=self.__close)
        b_ok.pack()

    def get_states(self):
        return [v.get() for v in self.states]

    def set_all(self):
        state = self.global_state.get()

        for x in self.states:
            x.set(state)

    def __close(self):
        self.return_data = self.get_states()
        self.destroy()


class ButtonsBox(tk.Toplevel):

    @staticmethod
    def execute[T](list_to_texts: list[T], title="", label: str | list[str] = "", parent=None,
                   width: int = 300) -> T | None:
        bb = ButtonsBox(list_to_texts, title=title, label=label, parent=parent, width=width)
        bb.wait_window()
        if bb.return_data is None:
            return None
        return list_to_texts[bb.return_data]

    def __init__[T](self, list_to_texts: list[T], title="", label: str | list[str] = "", parent=None, width: int = 300):
        super().__init__(parent)
        self.return_data = None

        self.parent = parent
        self.minsize(width, 200)
        self.title(title)

        if isinstance(label, str):
            ttk.Label(self, text=label).pack()
        else:
            for lab in label:
                ttk.Label(self, text=lab).pack()

        for i, val in enumerate(list_to_texts):
            button = ttk.Button(self, text=str(val), command=self.__close(i))
            button.pack()

    def __close(self, i):
        def f():
            self.return_data = i
            self.destroy()

        return f


class GeneratorDialog(tk.Toplevel):

    @staticmethod
    def execute(data_type: DataType,
                available_gens: list[GenType],
                defaults: dict[GenType, Any],
                parent=None) -> dict[GenType, int | float | bool] | None:
        bb = GeneratorDialog(data_type, available_gens, defaults, parent=parent)
        bb.wait_window()
        return bb.return_data

    def __init__(self,
                 data_type: DataType,
                 available_gens: list[GenType],
                 defaults: dict[GenType, Any],
                 parent=None):
        super().__init__(parent)
        self.return_data = None

        self.parent = parent
        self.title("Select settings")
        ttk.Label(self, text="Select settings for image generator").pack()
        ttk.Label(self, text=f"({data_type})").pack()

        self.settings: dict[GenType, Any] = dict()

        gen_types_order = list(sorted(GenType.get_types(), key=lambda x: x.value))

        for gen_type in gen_types_order:
            if gen_type not in available_gens:
                continue

            if gen_type == GenType.IMAGE:
                ttk.Label(self, text=gen_type.get_tip()).pack()
                scale_input = ttk.Entry(self)
                scale_input.insert(0, str(defaults[GenType.IMAGE]))
                scale_input.pack()

                self.settings.update({gen_type: scale_input})

            elif gen_type == GenType.TEXT_STROKE_WIDTH:
                ttk.Label(self, text=gen_type.get_tip()).pack()
                stroke_width_input = ttk.Entry(self)
                stroke_width_input.insert(0, str(defaults[GenType.TEXT_STROKE_WIDTH]))
                stroke_width_input.pack()

                self.settings.update({gen_type: stroke_width_input})

            else:
                bool_var = tk.BooleanVar()
                ttk.Checkbutton(self, text=gen_type.get_tip(), variable=bool_var, takefocus=False).pack()

                self.settings.update({gen_type: bool_var})

        ttk.Button(self, text="Start", command=self.__close).pack()

    def __close(self):
        self.return_data = {k: k.get_input_value(v.get()) for k, v in self.settings.items()}
        self.destroy()
