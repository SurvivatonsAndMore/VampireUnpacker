import multiprocessing

from Source.UI.ui_tkinter import UITkinter

def run_app():
    app = UITkinter()
    app.mainloop()

if __name__ == '__main__':
    multiprocessing.freeze_support()
    run_app()
