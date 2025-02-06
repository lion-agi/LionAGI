"""
Copyright 2024 HaiyangLi

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import inspect
from collections.abc import Callable
from typing import Any

from pydantic import Field, field_validator

from lionagi.protocols._concepts import Ordering
from lionagi.protocols.graph import Edge

from .work import Work
from .worker import Worker


class WorkEdge(Edge, Ordering[Work]):
    """
    Represents a directed edge between work tasks, responsible for transforming
    the result of one task into parameters for the next task.

    This class extends Edge to provide graph connectivity and Ordering to manage
    the sequence of work transformations.

    Attributes:
        convert_function (Callable): Function to transform the result of the previous
            work into parameters for the next work. This function must be decorated
            with the `worklink` decorator.
        convert_function_kwargs (dict): Additional parameters for the convert_function
            other than "from_work" and "from_result".
        associated_worker (Worker): The worker to which this WorkEdge belongs.
    """

    convert_function: Callable = Field(
        ...,
        description="Function to transform the result of the previous work into parameters for the next work",
    )

    convert_function_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description='Parameters for the worklink function other than "from_work" and "from_result"',
    )

    associated_worker: Worker = Field(
        ..., description="The worker to which this WorkEdge belongs"
    )

    @field_validator("convert_function", mode="before")
    def _validate_convert_function(cls, func: Callable) -> Callable:
        """
        Validates that the convert_function is decorated with the worklink decorator.

        Args:
            func (Callable): The function to validate.

        Returns:
            Callable: The validated function.

        Raises:
            ValueError: If the function is not decorated with the worklink decorator.
        """
        try:
            getattr(func, "_worklink_decorator_params")
            return func
        except AttributeError:
            raise ValueError(
                "convert_function must be a worklink decorated function"
            )

    @property
    def name(self) -> str:
        """
        Returns the name of the convert_function.

        Returns:
            str: The name of the convert_function.
        """
        return self.convert_function.__name__

    async def forward(self, task: Any) -> Work | None:
        """
        Transforms the result of the current work into parameters for the next work
        and schedules the next work task.

        Args:
            task (Any): The task to process.

        Returns:
            Work | None: The next work task to be executed, or None if no more steps
                are available.

        Raises:
            StopIteration: If the task has no available steps left to proceed.
        """
        if task.available_steps == 0:
            task.status_note = (
                "Task stopped proceeding further as all available steps have been used up, "
                "but the task has not yet reached completion."
            )
            return None

        func_signature = inspect.signature(self.convert_function)
        kwargs = self.convert_function_kwargs.copy()

        if "from_work" in func_signature.parameters:
            kwargs = {"from_work": task.current_work} | kwargs
        if "from_result" in func_signature.parameters:
            kwargs = {"from_result": task.current_work.result} | kwargs

        self.convert_function.auto_schedule = True
        next_work = await self.convert_function(
            self=self.associated_worker, **kwargs
        )
        return next_work

    def include(self, item: Work, /) -> None:
        """
        Include a work item in the edge's sequence.
        Required by Ordering protocol but not used in WorkEdge.

        Args:
            item (Work): The work item to include.
        """
        pass

    def exclude(self, item: Work, /) -> None:
        """
        Exclude a work item from the edge's sequence.
        Required by Ordering protocol but not used in WorkEdge.

        Args:
            item (Work): The work item to exclude.
        """
        pass
