from command_console import Command, parse_command


def test_parse_simple_state_command():
    assert parse_command("happy") == Command(name="happy", text="")


def test_parse_say_command_preserves_text():
    assert parse_command("say 你好 桌面") == Command(name="say", text="你好 桌面")


def test_parse_chat_command_preserves_text():
    assert parse_command("chat 今天怎么样") == Command(name="chat", text="今天怎么样")


def test_parse_quit_alias():
    assert parse_command("exit") == Command(name="quit", text="")


def test_parse_empty_line():
    assert parse_command("   ") == Command(name="empty", text="")


def test_parse_unknown_command():
    assert parse_command("dance now") == Command(name="unknown", text="dance now")
