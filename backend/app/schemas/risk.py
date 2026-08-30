from pydantic import BaseModel


class RuleResultOut(BaseModel):
    rule_id: str
    label: str
    weight: int
    triggered: bool
    reason: str | None


class RiskScoreOut(BaseModel):
    score: int
    rules_version: int
    results: list[RuleResultOut]
