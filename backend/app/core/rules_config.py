from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "rules" / "rules.yaml"


class RuleConfig(BaseModel):
    id: str
    label: str
    weight: int
    enabled: bool = True
    params: dict = {}


class RulesConfig(BaseModel):
    version: int
    rules: list[RuleConfig]


@lru_cache
def load_rules_config(path: Path = _DEFAULT_PATH) -> RulesConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    return RulesConfig(**data)
