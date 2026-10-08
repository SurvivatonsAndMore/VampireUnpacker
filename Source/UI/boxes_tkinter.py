import tkinter as tk
from tkinter import ttk


class CheckBoxes(tk.Toplevel):

    @staticmethod
    def execute[T](list_to_boxes: list[T], title="", label: str | list[str] = "", parent=None, width: int = 300) -> list[
        bool] | None:
        cbs = CheckBoxes(list_to_boxes, title=title, label=label, parent=parent, width=width)
        cbs.wait_window()
        return cbs.return_data

    def __init__[T](self, list_to_boxes: list[T], title="", label: str | list[str] = "", parent=None, width: int = 300):
        super().__init__(parent)
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
        self.return_data = None

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
        self.parent = parent
        self.minsize(width, 200)
        self.title(title)

        if isinstance(label, str):
            ttk.Label(self, text=label).pack()
        else:
            for lab in label:
                ttk.Label(self, text=lab).pack()

        self.return_data = None

        for i, val in enumerate(list_to_texts):
            button = ttk.Button(self, text=str(val), command=self.__close(i))
            button.pack()

    def __close(self, i):
        def f():
            self.return_data = i
            self.destroy()

        return f
