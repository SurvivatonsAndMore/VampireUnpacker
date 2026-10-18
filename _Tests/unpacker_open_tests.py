from unittest import TestCase, main as ut_main

from Source.UI import ui_tkinter


class UnpackerOpenTest(TestCase):
    def test_open_unpacker_tkinter(self):
        unp = ui_tkinter.UITkinter()
        self.assertEqual(unp.state(), "normal")
        unp.destroy()

if __name__ == "__main__":
    ut_main()