import json
import re
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def aliases() -> dict[str, str]:
    path = files("cookkg").joinpath("resources/aliases.json")
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_ingredient(raw: str) -> str:
    value = raw.strip().lstrip("-* ").strip()
    value = re.sub(r"[（(](?:可选|选用)[）)]", "", value).strip()
    value = re.split(r"\s*[=＝]\s*", value, maxsplit=1)[0]
    value = re.sub(
        r"\s+\d+(?:\.\d+)?(?:\s*[-~至]\s*\d+(?:\.\d+)?)?\s*"
        r"(?:g|kg|ml|L|克|千克|毫升|升|个|只|颗|根|片|勺|茶匙|汤匙|块|瓣|张|斤).*$",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip()
    return aliases().get(value, value)
