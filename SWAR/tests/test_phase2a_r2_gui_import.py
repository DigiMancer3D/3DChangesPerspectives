def test_shell_window_class_exists_for_launcher():
    import swar.gui_shell as gui_shell
    assert hasattr(gui_shell, "SwarShellWindow")
