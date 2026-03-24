from enum import StrEnum


class SearchStrategy(StrEnum):
    RULE_BASED = "rule_based"
    VECTOR = "vector"
    HYBRID = "hybrid"
