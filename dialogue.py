import random
from typing import Dict, List


class LocalDialogue:
    def __init__(self) -> None:
        self.categories: Dict[str, List[str]] = {
            "greeting": [
                "你好，我在这里。",
                "嗨，今天也一起待一会儿。",
                "你好呀，我刚刚醒来。",
            ],
            "status": [
                "我现在状态不错。",
                "我正在观察桌面。",
                "我有点想动一动。",
            ],
            "companionship": [
                "我陪你待着。",
                "我们一起安静一会儿。",
                "我会在屏幕边上陪你。",
            ],
            "encouragement": [
                "慢慢来，先做眼前这一小步。",
                "辛苦了，可以先缓一缓。",
                "你已经在推进了。",
            ],
            "default": [
                "我听到了。",
                "这个我先记在心里。",
                "嗯，我在看着你操作。",
            ],
        }
        self.keyword_map = {
            "greeting": ("你好", "hello", "hi"),
            "status": ("你好吗", "怎么样"),
            "companionship": ("无聊", "陪我"),
            "encouragement": ("累", "压力", "加油"),
        }
        self.menu_map = {
            "greeting": "greeting",
            "status": "status",
            "company": "companionship",
            "encourage": "encouragement",
            "random": "default",
        }

    def reply_for_text(self, text: str) -> str:
        normalized = text.strip().lower()
        for category, keywords in self.keyword_map.items():
            if any(keyword.lower() in normalized for keyword in keywords):
                return self._pick(category)
        return self._pick("default")

    def reply_for_menu(self, action: str, current_state: str = "idle") -> str:
        if action == "status":
            return f"我现在是 {current_state} 状态。"
        category = self.menu_map.get(action, "default")
        return self._pick(category)

    def _pick(self, category: str) -> str:
        return random.choice(self.categories[category])
