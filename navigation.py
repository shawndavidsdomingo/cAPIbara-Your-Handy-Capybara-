"""Decides which window is on screen (Login, Register or Main).

Windows never create each other. They just call go_login(), go_register()
or go_main(username) from here.

The window classes are imported INSIDE the functions on purpose: the windows
import this module, so importing them at the top would be a circular import.
"""

_current = None    # the window on screen now
_previous = None   # the window closed one step ago. It is kept alive on purpose:
                   # Python deletes a window nobody refers to, and we must not
                   # delete a window while one of its own buttons is still running.


def _show(window):
    global _current, _previous
    window.show()                      # show the new one first, so the app never has 0 windows
    if _current is not None:
        _current.close()
    _previous, _current = _current, window


def go_login():
    from login_window import LoginWindow
    _show(LoginWindow())


def go_register():
    from register_window import RegisterWindow
    _show(RegisterWindow())


def go_main(username):
    from main_window import MainWindow
    _show(MainWindow(username))