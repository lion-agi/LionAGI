# Copyright (c) 2023 - 2024, HaiyangLi <quantocean.li at gmail dot com>
#
# SPDX-License-Identifier: Apache-2.0

import re
from collections.abc import Sequence
from typing import Any, TypeAlias, TypeVar

from pydantic import BaseModel, Field, field_validator

from lionagi.libs.parse import (
    fuzzy_parse_json,
    to_dict,
    to_json,
    validate_boolean,
)
from lionagi.protocols.models import FieldModel

from .prompts import (
    action_requests_field_description,
    action_required_field_description,
    arguments_field_description,
    function_field_description,
)

# Type aliases
JsonDict: TypeAlias = dict[str, Any]
ValidatorType = TypeVar("ValidatorType")
ActionList: TypeAlias = list[JsonDict]


__all__ = (
    "ActionRequestModel",
    "ActionResponseModel",
    "ACTION_REQUESTS_FIELD_MODEL",
    "ACTION_RESPONSES_FIELD_MODEL",
)


def parse_action_request(content: str | JsonDict | BaseModel) -> ActionList:
    """Parse action request from various input formats."""

    json_blocks = []

    if isinstance(content, BaseModel):
        json_blocks = [content.model_dump()]

    elif isinstance(content, str):
        json_blocks = to_json(content, fuzzy_parse=True)
        if not json_blocks:
            pattern2 = r"```python\s*(.*?)\s*```"
            _d = re.findall(pattern2, content, re.DOTALL)
            json_blocks = []
            for match in _d:
                if a := fuzzy_parse_json(match):
                    json_blocks.append(a)

    elif content and isinstance(content, dict):
        json_blocks = [content]

    if json_blocks and not isinstance(json_blocks, list):
        json_blocks = [json_blocks]

    out = []

    for i in json_blocks:
        print(i)
        j = {}
        if isinstance(i, dict):
            if "function" in i and isinstance(i["function"], dict):
                if "name" in i["function"]:
                    i = i["function"]
            for k, v in i.items():
                k = (
                    k.replace("action_", "")
                    .replace("recipient_", "")
                    .replace("s", "")
                )
                if k in ["name", "function", "recipient"]:
                    j["function"] = v
                elif k in ["parameter", "argument", "arg"]:
                    j["arguments"] = fuzzy_parse_json(v)
            if (
                j
                and all(key in j for key in ["function", "arguments"])
                and j["arguments"]
            ):
                out.append(j)

    return out


def _validate_function_name(cls, value: Any) -> str | None:
    """Validate function name is string type."""
    return value if isinstance(value, str) else None


def _validate_action_required(cls, value: Any) -> bool:
    """Validate and convert action required flag."""
    try:
        return validate_boolean(value)
    except Exception:
        return False


def _validate_arguments(cls, value: Any) -> JsonDict:
    """Validate and parse arguments to dictionary."""
    return to_dict(
        value,
        fuzzy_parse=True,
        suppress=True,
        recursive=True,
        recursive_python_only=False,
    )


# Field models
FUNCTION_FIELD_MODEL = FieldModel(
    name="function",
    default=None,
    annotation=str | None,
    title="Function",
    description=function_field_description,
    examples=["add", "multiply", "divide"],
    validator=_validate_function_name,
)

ARGUMENTS_FIELD_MODEL = FieldModel(
    name="arguments",
    annotation=dict | None,
    default_factory=dict,
    title="Action Arguments",
    description=arguments_field_description,
    examples=[{"num1": 1, "num2": 2}, {"x": "hello", "y": "world"}],
    validator=_validate_arguments,
    validator_kwargs={"mode": "before"},
)

ACTION_REQUIRED_FIELD_MODEL = FieldModel(
    name="action_required",
    annotation=bool,
    default=False,
    title="Action Required",
    description=action_required_field_description,
    validator=_validate_action_required,
    validator_kwargs={"mode": "before"},
)


class ActionRequestModel(BaseModel):
    """Model for action requests with function name and arguments."""

    function: str | None = FUNCTION_FIELD_MODEL.field_info
    arguments: dict[str, Any] | None = ARGUMENTS_FIELD_MODEL.field_info

    @field_validator("arguments", mode="before")
    def validate_arguments(cls, value: Any) -> dict[str, Any]:
        return _validate_arguments(cls, value)

    @classmethod
    def create(cls, content: str) -> Sequence[BaseModel]:
        """Create request models from content string."""
        try:
            requests = parse_action_request(content)
            return (
                [cls.model_validate(req) for req in requests]
                if requests
                else []
            )
        except Exception:
            return []


class ActionResponseModel(BaseModel):

    function: str = Field(default_factory=str)
    arguments: dict[str, Any] = Field(default_factory=dict)
    output: Any = None


# Field definitions for action collections
ACTION_REQUESTS_FIELD_MODEL = FieldModel(
    name="action_requests",
    annotation=list[ActionRequestModel],
    default_factory=list,
    title="Actions",
    description=action_requests_field_description,
)

ACTION_RESPONSES_FIELD_MODEL = FieldModel(
    name="action_responses",
    annotation=list[ActionResponseModel],
    default_factory=list,
    title="Actions",
    description="**do not fill**",
)
