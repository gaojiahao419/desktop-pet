import json
import urllib.parse
import urllib.request


class PetAiClient:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        path: str = "/chat",
        timeout: int = 60,
    ) -> None:
        self.host = host
        self.port = port
        self.path = path
        self.timeout = timeout

    def reply(self, message: str) -> str:
        payload = json.dumps(
            {"message": message},
            ensure_ascii=False,
        ).encode("utf-8")

        url = urllib.parse.urlunparse(
            ("http", f"{self.host}:{self.port}", self.path, "", "", "")
        )

        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))

        reply = str(data.get("reply", "")).strip()
        if not reply:
            raise RuntimeError("empty AI reply")
        return reply