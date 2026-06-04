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
    reply = dialogue.reply_for_menu("status", current_state="sleep")
    assert "sleep" in reply


def test_unknown_menu_action_returns_default_reply():
    dialogue = LocalDialogue()
    reply = dialogue.reply_for_menu("unknown", current_state="idle")
    assert reply in dialogue.categories["default"]
