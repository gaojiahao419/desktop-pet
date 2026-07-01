from dialogue import LocalDialogue


def test_keyword_greeting_reply():
    dialogue = LocalDialogue()
    reply = dialogue.reply_for_text("你好呀")
    assert reply in dialogue.categories["greeting"]


def test_keyword_encouragement_reply():
    dialogue = LocalDialogue()
    reply = dialogue.reply_for_text("今天有点累")
    assert reply in dialogue.categories["encouragement"]


def test_menu_status_uses_current_state():
    dialogue = LocalDialogue()
    reply = dialogue.reply_for_menu("status", current_state="happy")
    assert "开心" in reply


def test_menu_status_displays_sleep_state():
    dialogue = LocalDialogue()

    assert "睡觉" in dialogue.reply_for_menu("status", current_state="sleep")


def test_menu_status_falls_back_for_removed_walk_state():
    dialogue = LocalDialogue()

    assert "walk" not in dialogue.reply_for_menu("status", current_state="walk")


def test_unknown_menu_action_returns_default_reply():
    dialogue = LocalDialogue()
    reply = dialogue.reply_for_menu("unknown", current_state="idle")
    assert reply in dialogue.categories["default"]
