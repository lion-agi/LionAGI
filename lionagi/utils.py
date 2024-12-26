import ast
import asyncio
import contextlib
import copy as _copy
import importlib.metadata
import importlib.util
import json
import logging
import os
import re
import uuid
from abc import ABC
from collections.abc import (
    AsyncGenerator,
    Callable,
    Iterable,
    Mapping,
    Sequence,
)
from datetime import datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Self, TypedDict, TypeVar, overload

from pydantic import BaseModel, model_validator
from pydantic_core import PydanticUndefinedType

R = TypeVar("R")
T = TypeVar("T")


logger = logging.getLogger(
    __name__, level=logging.INFO, format="%(asctime)s - %(message)s"
)


__all__ = (
    "UndefinedType",
    "KeysDict",
    "LionModel",
    "Params",
    "DataClass",
    "UNDEFINED",
    "copy",
    "is_same_dtype",
    "get_file_classes",
    "get_class_file_registry",
    "get_class_objects",
    "is_coro_func",
    "custom_error_handler",
    "to_list",
    "lcall",
    "alcall",
    "bcall",
    "tcall",
    "create_path",
    "create_instruct_collection_model_params",
    "time",
    "get_class_file_registry",
    "get_class_objects",
    "get_file_classes",
    "is_same_dtype",
    "get_class_file_registry",
    "get_class_objects",
    "get_file_classes",
    "fuzzy_parse_json",
    "fix_json_string",
    "ToListParams",
    "LCallParams",
    "ALCallParams",
    "BCallParams",
    "TCallParams",
    "CreatePathParams",
)


# --- General Global Utilities Types ---


class UndefinedType:
    def __init__(self) -> None:
        self.undefined = True

    def __bool__(self) -> Literal[False]:
        return False

    def __deepcopy__(self, memo):
        # Ensure UNDEFINED is universal
        return self

    def __repr__(self) -> Literal["UNDEFINED"]:
        return "UNDEFINED"

    __slots__ = ["undefined"]


class KeysDict(TypedDict, total=False):
    """TypedDict for keys dictionary."""

    key: Any  # Represents any key-type pair


class LionModel(BaseModel):

    def to_dict(self, **kwargs) -> dict:
        """provides interface, specific methods need to be implemented in subclass kwargs for pydantic model_dump"""
        return self.model_dump(**kwargs)

    @classmethod
    def from_dict(cls, data: dict, **kwargs) -> Self:
        """provides interface, specific methods need to be implemented in subclass kwargs for pydantic model_validate"""
        return cls.model_validate(data, **kwargs)


class Params(BaseModel):

    def keys(self):
        return self.model_fields.keys()

    def __call__(self, *args, **kwargs):
        raise NotImplementedError(
            "This method should be implemented in a subclass"
        )


class DataClass(ABC):
    pass


# --- Create a global UNDEFINED object ---
UNDEFINED = UndefinedType()


# --- General Global Utilities Functions ---
def copy(obj: T, /, *, deep: bool = True, num: int = 1) -> T | list[T]:
    if num < 1:
        raise ValueError("Number of copies must be at least 1")

    copy_func = _copy.deepcopy if deep else _copy.copy
    return [copy_func(obj) for _ in range(num)] if num > 1 else copy_func(obj)


def is_same_dtype(
    input_: list[T] | dict[Any, T],
    dtype: type | None = None,
    return_dtype: bool = False,
) -> bool | tuple[bool, type | None]:
    if not input_:
        # If empty, trivially true. dtype is None since no elements exist.
        return (True, None) if return_dtype else True

    if isinstance(input_, Mapping):
        # For dictionaries, use values
        values_iter = iter(input_.values())
        first_val = next(values_iter, None)
        if dtype is None:
            dtype = type(first_val) if first_val is not None else None
        # Check the first element
        result = (dtype is None or isinstance(first_val, dtype)) and all(
            isinstance(v, dtype) for v in values_iter
        )
    else:
        # For lists (or list-like), directly access the first element
        first_val = input_[0]
        if dtype is None:
            dtype = type(first_val) if first_val is not None else None
        # Check all elements including the first
        result = all(isinstance(e, dtype) for e in input_)

    return (result, dtype) if return_dtype else result


def get_file_classes(file_path):
    with open(file_path) as file:
        file_content = file.read()

    tree = ast.parse(file_content)

    class_file_dict = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_file_dict[node.name] = file_path

    return class_file_dict


def get_class_file_registry(folder_path, pattern_list):
    class_file_registry = {}
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".py"):
                if any(pattern in root for pattern in pattern_list):
                    class_file_dict = get_file_classes(
                        os.path.join(root, file)
                    )
                    class_file_registry.update(class_file_dict)
    return class_file_registry


def get_class_objects(file_path):
    class_objects = {}
    spec = importlib.util.spec_from_file_location("module.name", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for class_name in dir(module):
        obj = getattr(module, class_name)
        if isinstance(obj, type):
            class_objects[class_name] = obj

    return class_objects


@lru_cache(maxsize=None)
def is_coro_func(func: Callable[..., Any]) -> bool:
    return asyncio.iscoroutinefunction(func)


async def custom_error_handler(
    error: Exception, error_map: dict[type, Callable[[Exception], None]]
) -> None:
    if type(error) in error_map:
        if is_coro_func(error_map[type(error)]):
            return await error_map[type(error)](error)
        return error_map[type(error)](error)
    logging.error(f"Unhandled error: {error}")
    raise error


@overload
def to_list(
    input_: None | UndefinedType | PydanticUndefinedType,
    /,
) -> list: ...


@overload
def to_list(
    input_: str | bytes | bytearray,
    /,
    use_values: bool = False,
) -> list[str | bytes | bytearray]: ...


@overload
def to_list(
    input_: Mapping,
    /,
    use_values: bool = False,
) -> list[Any]: ...


@overload
def to_list(
    input_: Any,
    /,
    *,
    flatten: bool = False,
    dropna: bool = False,
    unique: bool = False,
    use_values: bool = False,
    flatten_tuple_set: bool = False,
) -> list: ...


def to_list(
    input_: Any,
    /,
    *,
    flatten: bool = False,
    dropna: bool = False,
    unique: bool = False,
    use_values: bool = False,
    flatten_tuple_set: bool = False,
) -> list:
    """Convert input to a list with optional transformations.

    Transforms various input types into a list with configurable processing
    options for flattening, filtering, and value extraction.

    Args:
        input_: Value to convert to list.
        flatten: If True, recursively flatten nested iterables.
        dropna: If True, remove None and undefined values.
        unique: If True, remove duplicates (requires flatten=True).
        use_values: If True, extract values from enums/mappings.
        flatten_tuple_items: If True, include tuples in flattening.
        flatten_set_items: If True, include sets in flattening.

    Returns:
        list: Processed list based on input and specified options.

    Raises:
        ValueError: If unique=True is used without flatten=True.

    Examples:
        >>> to_list([1, [2, 3], 4], flatten=True)
        [1, 2, 3, 4]
        >>> to_list([1, None, 2], dropna=True)
        [1, 2]
    """

    def _process_list(
        lst: list[Any],
        flatten: bool,
        dropna: bool,
    ) -> list[Any]:
        """Process list according to flatten and dropna options.

        Args:
            lst: Input list to process.
            flatten: Whether to flatten nested iterables.
            dropna: Whether to remove None/undefined values.

        Returns:
            list: Processed list based on specified options.
        """
        result = []
        skip_types = (str, bytes, bytearray, Mapping, BaseModel, Enum)

        if not flatten_tuple_set:
            skip_types += (tuple, set, frozenset)

        for item in lst:
            if dropna and (
                item is None
                or isinstance(item, (UndefinedType, PydanticUndefinedType))
            ):
                continue

            is_iterable = isinstance(item, Iterable)
            should_skip = isinstance(item, skip_types)

            if is_iterable and not should_skip:
                item_list = list(item)
                if flatten:
                    result.extend(
                        _process_list(
                            item_list, flatten=flatten, dropna=dropna
                        )
                    )
                else:
                    result.append(
                        _process_list(
                            item_list, flatten=flatten, dropna=dropna
                        )
                    )
            else:
                result.append(item)

        return result

    def _to_list_type(input_: Any, use_values: bool) -> list[Any]:
        """Convert input to initial list based on type.

        Args:
            input_: Value to convert to list.
            use_values: Whether to extract values from containers.

        Returns:
            list: Initial list conversion of input.
        """
        if input_ is None or isinstance(
            input_, (UndefinedType, PydanticUndefinedType)
        ):
            return []

        if isinstance(input_, list):
            return input_

        if isinstance(input_, type) and issubclass(input_, Enum):
            members = input_.__members__.values()
            return (
                [member.value for member in members]
                if use_values
                else list(members)
            )

        if isinstance(input_, (str, bytes, bytearray)):
            return list(input_) if use_values else [input_]

        if isinstance(input_, Mapping):
            return (
                list(input_.values())
                if use_values and hasattr(input_, "values")
                else [input_]
            )

        if isinstance(input_, BaseModel):
            return [input_]

        if isinstance(input_, Iterable) and not isinstance(
            input_, (str, bytes, bytearray)
        ):
            return list(input_)

        return [input_]

    if unique and not flatten:
        raise ValueError("unique=True requires flatten=True")

    initial_list = _to_list_type(input_, use_values=use_values)
    processed = _process_list(initial_list, flatten=flatten, dropna=dropna)

    if unique:
        seen = set()
        return [x for x in processed if not (x in seen or seen.add(x))]

    return processed


class ToListParams(Params):
    flatten: bool = False
    dropna: bool = False
    unique: bool = False
    use_values: bool = False
    flatten_tuple_set: bool = False

    def __call__(self, input_: Any):
        return to_list(
            input_,
            flatten=self.flatten,
            dropna=self.dropna,
            unique=self.unique,
            use_values=self.use_values,
            flatten_tuple_set=self.flatten_tuple_set,
        )


def lcall(
    input_: Iterable[T] | T,
    func: Callable[[T], R] | Iterable[Callable[[T], R]],
    /,
    *args: Any,
    sanitize_input: bool = False,
    unique_input: bool = False,
    flatten: bool = False,
    dropna: bool = False,
    unique_output: bool = False,
    flatten_tuple_set: bool = False,
    **kwargs: Any,
) -> list[R]:
    """Apply function to each element in input list with optional processing.

    Maps a function over input elements and processes results. Can sanitize input
    and output using various filtering options.

    Args:
        input_: Single item or iterable to process.
        func: Function to apply or single-item iterable containing function.
        *args: Additional positional arguments passed to func.
        sanitize_input: If True, sanitize input using to_list.
        unique_input: If True with sanitize_input, remove input duplicates.
        flatten: If True, flatten output nested structures.
        dropna: If True, remove None values from output.
        unique_output: If True with flatten/dropna, remove output duplicates.
        flatten_tuple_set: If True, flatten tuples and sets.
        **kwargs: Additional keyword arguments passed to func.

    Returns:
        list: Results of applying func to each input element.

    Raises:
        ValueError: If func is not callable or unique_output used incorrectly.
        TypeError: If func or input processing fails.

    Examples:
        >>> lcall([1, 2, 3], str)
        ['1', '2', '3']
        >>> lcall([1, [2, 3]], str, flatten=True)
        ['1', '2', '3']
    """
    # Validate and extract callable function
    if not callable(func):
        try:
            func_list = list(func)
            if len(func_list) != 1 or not callable(func_list[0]):
                raise ValueError(
                    "func must contain exactly one callable function."
                )
            func = func_list[0]
        except TypeError as e:
            raise ValueError(
                "func must be callable or iterable with one callable."
            ) from e

    # Process input based on sanitization flag
    if sanitize_input:
        input_ = to_list(
            input_,
            flatten=True,
            dropna=True,
            unique=unique_input,
            flatten_tuple_set=flatten_tuple_set,
        )
    else:
        if not isinstance(input_, list):
            try:
                input_ = list(input_)
            except TypeError:
                input_ = [input_]

    # Validate output processing options
    if unique_output and not (flatten or dropna):
        raise ValueError(
            "unique_output requires flatten or dropna for post-processing."
        )

    # Process elements and collect results
    out = []
    append = out.append

    for item in input_:
        try:
            result = func(item, *args, **kwargs)
            append(result)
        except InterruptedError:
            return out
        except Exception:
            raise

    # Apply output processing if requested
    if flatten or dropna:
        out = to_list(
            out,
            flatten=flatten,
            dropna=dropna,
            unique=unique_output,
            flatten_tuple_set=flatten_tuple_set,
        )

    return out


class CallParams(Params):
    """params class for high order function with additional handling of lower order function parameters, can take arbitrary number of args and kwargs, args need to be in agrs=, kwargs can be passed as is"""

    args: list = []
    kwargs: dict = {}

    @model_validator(mode="before")
    def _validate_data(cls, data: dict):
        _d = {}
        for k in list(data.keys()):
            if k in cls.keys():
                _d[k] = data.pop(k)
        _d.setdefault("args", [])
        _d.setdefault("kwargs", {})
        _d["kwargs"].update(data)
        return _d

    def __call__(self, *args, **kwargs):
        raise NotImplementedError(
            "This method should be implemented in a subclass"
        )


class LCallParams(CallParams):
    func: Any = None
    sanitize_input: bool = False
    unique_input: bool = False
    flatten: bool = False
    dropna: bool = False
    unique_output: bool = False
    flatten_tuple_set: bool = False

    def __call__(self, input_: Any, func=None):
        if self.func is None and func is None:
            raise ValueError("a sync func must be provided")
        return lcall(
            input_,
            func or self.func,
            *self.args,
            sanitize_input=self.sanitize_input,
            unique_input=self.unique_input,
            flatten=self.flatten,
            dropna=self.dropna,
            unique_output=self.unique_output,
            flatten_tuple_set=self.flatten_tuple_set,
            **self.kwargs,
        )


async def alcall(
    input_: list[Any],
    func: Callable[..., T],
    /,
    *,
    sanitize_input: bool = False,
    unique_input: bool = False,
    num_retries: int = 0,
    initial_delay: float = 0,
    retry_delay: float = 0,
    backoff_factor: float = 1,
    retry_default: Any = UNDEFINED,
    retry_timeout: float | None = None,
    retry_timing: bool = False,
    max_concurrent: int | None = None,
    throttle_period: float | None = None,
    flatten: bool = False,
    dropna: bool = False,
    unique_output: bool = False,
    flatten_tuple_set: bool = False,
    **kwargs: Any,
) -> list[T] | list[tuple[T, float]]:
    """
    Asynchronously apply a function to each element of a list, with optional input sanitization,
    retries, timeout, and output processing.

    Args:
        input_ (list[Any]): The list of inputs to process.
        func (Callable[..., T]): The function to apply (async or sync).
        sanitize_input (bool): If True, input is flattened, dropna applied, and made unique if unique_input.
        unique_input (bool): If True and sanitize_input is True, input is made unique.
        num_retries (int): Number of retry attempts on exception.
        initial_delay (float): Initial delay before starting executions.
        retry_delay (float): Delay between retries.
        backoff_factor (float): Multiplier for delay after each retry.
        retry_default (Any): Default value if all retries fail.
        retry_timeout (float | None): Timeout for each function call.
        retry_timing (bool): If True, return (result, duration) tuples.
        max_concurrent (int | None): Maximum number of concurrent operations.
        throttle_period (float | None): Delay after each completed operation.
        flatten (bool): Flatten the final result if True.
        dropna (bool): Remove None values from the final result if True.
        unique_output (bool): Deduplicate the output if True.
        **kwargs: Additional arguments passed to func.

    Returns:
        list[T] or list[tuple[T, float]]: The processed results, or results with timing if retry_timing is True.

    Raises:
        asyncio.TimeoutError: If a call times out and no default is provided.
        Exception: If retries are exhausted and no default is provided.
    """

    # Validate func is a single callable
    if not callable(func):
        # If func is not callable, maybe it's an iterable. Extract one callable if possible.
        try:
            func_list = list(func)  # Convert iterable to list
        except TypeError:
            raise ValueError(
                "func must be callable or an iterable containing one callable."
            )

        # Ensure exactly one callable is present
        if len(func_list) != 1 or not callable(func_list[0]):
            raise ValueError("Only one callable function is allowed.")

        func = func_list[0]

    # Process input if requested
    if sanitize_input:
        input_ = to_list(
            input_,
            flatten=True,
            dropna=True,
            unique=unique_input,
            flatten_tuple_set=flatten_tuple_set,
        )
    else:
        if not isinstance(input_, list):
            # Attempt to iterate
            try:
                iter(input_)
                # It's iterable (tuple), convert to list of its contents
                input_ = list(input_)
            except TypeError:
                # Not iterable, just wrap in a list
                input_ = [input_]

    # Optional initial delay before processing
    if initial_delay:
        await asyncio.sleep(initial_delay)

    semaphore = asyncio.Semaphore(max_concurrent) if max_concurrent else None
    throttle_delay = throttle_period or 0
    coro_func = is_coro_func(func)

    async def call_func(item: Any) -> T:
        if coro_func:
            # Async function
            if retry_timeout is not None:
                return await asyncio.wait_for(
                    func(item, **kwargs), timeout=retry_timeout
                )
            else:
                return await func(item, **kwargs)
        else:
            # Sync function
            if retry_timeout is not None:
                return await asyncio.wait_for(
                    asyncio.to_thread(func, item, **kwargs),
                    timeout=retry_timeout,
                )
            else:
                return func(item, **kwargs)

    async def execute_task(i: Any, index: int) -> Any:
        start_time = asyncio.get_running_loop().time()
        attempts = 0
        current_delay = retry_delay
        while True:
            try:
                result = await call_func(i)
                if retry_timing:
                    end_time = asyncio.get_running_loop().time()
                    return index, result, end_time - start_time
                else:
                    return index, result
            except Exception:
                attempts += 1
                if attempts <= num_retries:
                    if current_delay:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff_factor
                    # Retry loop continues
                else:
                    # Exhausted retries
                    if retry_default is not UNDEFINED:
                        # Return default if provided
                        if retry_timing:
                            end_time = asyncio.get_running_loop().time()
                            duration = end_time - (start_time or end_time)
                            return index, retry_default, duration
                        else:
                            return index, retry_default
                    # No default, re-raise
                    raise

    async def task_wrapper(item: Any, idx: int) -> Any:
        if semaphore:
            async with semaphore:
                return await execute_task(item, idx)
        else:
            return await execute_task(item, idx)

    # Create tasks
    tasks = [task_wrapper(item, idx) for idx, item in enumerate(input_)]

    # Collect results as they complete
    results = []
    for coro in asyncio.as_completed(tasks):
        res = await coro
        results.append(res)
        if throttle_delay:
            await asyncio.sleep(throttle_delay)

    # Sort by original index
    results.sort(key=lambda x: x[0])

    if retry_timing:
        # (index, result, duration)
        filtered = [
            (r[1], r[2]) for r in results if not dropna or r[1] is not None
        ]
        return filtered
    else:
        # (index, result)
        output_list = [r[1] for r in results]
        return to_list(
            output_list,
            flatten=flatten,
            dropna=dropna,
            unique=unique_output,
            flatten_tuple_set=flatten_tuple_set,
        )


class ALCallParams(CallParams):
    func: Any = None
    sanitize_input: bool = False
    unique_input: bool = False
    num_retries: int = 0
    initial_delay: float = 0
    retry_delay: float = 0
    backoff_factor: float = 1
    retry_default: Any = UNDEFINED
    retry_timeout: float | None = None
    retry_timing: bool = False
    max_concurrent: int | None = None
    throttle_period: float | None = None
    flatten: bool = False
    dropna: bool = False
    unique_output: bool = False
    flatten_tuple_set: bool = False

    async def __call__(self, input_: Any, func=None):
        if self.func is None and func is None:
            raise ValueError("a sync/async func must be provided")
        return await alcall(
            input_,
            func or self.func,
            *self.args,
            sanitize_input=self.sanitize_input,
            unique_input=self.unique_input,
            num_retries=self.num_retries,
            initial_delay=self.initial_delay,
            retry_delay=self.retry_delay,
            backoff_factor=self.backoff_factor,
            retry_default=self.retry_default,
            retry_timeout=self.retry_timeout,
            retry_timing=self.retry_timing,
            max_concurrent=self.max_concurrent,
            throttle_period=self.throttle_period,
            flatten=self.flatten,
            dropna=self.dropna,
            unique_output=self.unique_output,
            flatten_tuple_set=self.flatten_tuple_set,
            **self.kwargs,
        )


async def bcall(
    input_: Any,
    func: Callable[..., T],
    /,
    batch_size: int,
    *,
    sanitize_input: bool = False,
    unique_input: bool = False,
    num_retries: int = 0,
    initial_delay: float = 0,
    retry_delay: float = 0,
    backoff_factor: float = 1,
    retry_default: Any = UNDEFINED,
    retry_timeout: float | None = None,
    retry_timing: bool = False,
    max_concurrent: int | None = None,
    throttle_period: float | None = None,
    flatten: bool = False,
    dropna: bool = False,
    unique_output: bool = False,
    flatten_tuple_set: bool = False,
    **kwargs: Any,
) -> AsyncGenerator[list[T | tuple[T, float]], None]:

    input_ = to_list(input_, flatten=True, dropna=True)

    for i in range(0, len(input_), batch_size):
        batch = input_[i : i + batch_size]  # noqa: E203
        yield await alcall(
            batch,
            func,
            sanitize_input=sanitize_input,
            unique_input=unique_input,
            num_retries=num_retries,
            initial_delay=initial_delay,
            retry_delay=retry_delay,
            backoff_factor=backoff_factor,
            retry_default=retry_default,
            retry_timeout=retry_timeout,
            retry_timing=retry_timing,
            max_concurrent=max_concurrent,
            throttle_period=throttle_period,
            flatten=flatten,
            dropna=dropna,
            unique_output=unique_output,
            flatten_tuple_set=flatten_tuple_set,
            **kwargs,
        )


class BCallParams(CallParams):
    func: Any = None
    batch_size: int
    sanitize_input: bool = False
    unique_input: bool = False
    num_retries: int = 0
    initial_delay: float = 0
    retry_delay: float = 0
    backoff_factor: float = 1
    retry_default: Any = UNDEFINED
    retry_timeout: float | None = None
    retry_timing: bool = False
    max_concurrent: int | None = None
    throttle_period: float | None = None
    flatten: bool = False
    dropna: bool = False
    unique_output: bool = False
    flatten_tuple_set: bool = False

    async def __call__(self, input_, func=None):
        if self.func is None and func is None:
            raise ValueError("a sync/async func must be provided")
        return await bcall(
            input_,
            func or self.func,
            *self.args,
            batch_size=self.batch_size,
            sanitize_input=self.sanitize_input,
            unique_input=self.unique_input,
            num_retries=self.num_retries,
            initial_delay=self.initial_delay,
            retry_delay=self.retry_delay,
            backoff_factor=self.backoff_factor,
            retry_default=self.retry_default,
            retry_timeout=self.retry_timeout,
            retry_timing=self.retry_timing,
            max_concurrent=self.max_concurrent,
            throttle_period=self.throttle_period,
            flatten=self.flatten,
            dropna=self.dropna,
            unique_output=self.unique_output,
            flatten_tuple_set=self.flatten_tuple_set,
            **self.kwargs,
        )


async def tcall(
    func: Callable[..., T],
    /,
    *args: Any,
    initial_delay: float = 0,
    timing: bool = False,
    timeout: float | None = None,
    default: Any = UNDEFINED,
    error_msg: str | None = None,
    error_map: dict[type, Callable[[Exception], None]] | None = None,
    **kwargs: Any,
) -> T | tuple[T, float]:
    """Execute a function asynchronously with timing and error handling.

    Executes a synchronous or asynchronous function with optional timing,
    timeout, and error handling capabilities. Can delay execution and provide
    detailed error feedback.

    Args:
        func: Function or coroutine to execute.
        *args: Positional arguments passed to func.
        initial_delay: Seconds to wait before execution. Defaults to 0.
        timing: If True, returns tuple of (result, duration). Defaults to False.
        timeout: Maximum seconds to wait for completion. None for no timeout.
        default: Value returned on error if provided, otherwise error is raised.
        error_msg: Optional prefix for error messages.
        error_map: Dict mapping exception types to handler functions.
        **kwargs: Keyword arguments passed to func.

    Returns:
        If timing=False:
            Result of func execution or default value on error
        If timing=True:
            Tuple of (result, duration_in_seconds)

    Raises:
        asyncio.TimeoutError: If execution exceeds timeout and no default set.
        RuntimeError: If execution fails and no default or handler exists.

    Examples:
        >>> async def example():
        ...     result = await tcall(
        ...         slow_function,
        ...         timeout=5,
        ...         default="timeout",
        ...         timing=True
        ...     )
        ...     print(result)  # ("result", 1.234) or ("timeout", 5.0)
    """
    loop = asyncio.get_running_loop()
    start = loop.time()

    def finalize(result: Any) -> Any:
        """Wrap result with timing information if requested."""
        if timing:
            duration = loop.time() - start
            return (result, duration)
        return result

    try:
        if initial_delay > 0:
            await asyncio.sleep(initial_delay)

        if is_coro_func(func):
            # Handle coroutine function
            if timeout is not None:
                result = await asyncio.wait_for(
                    func(*args, **kwargs), timeout=timeout
                )
            else:
                result = await func(*args, **kwargs)
        else:
            # Handle synchronous function
            if timeout is not None:
                coro = asyncio.to_thread(func, *args, **kwargs)
                result = await asyncio.wait_for(coro, timeout=timeout)
            else:
                result = func(*args, **kwargs)

        return finalize(result)

    except TimeoutError as e:
        if default is not UNDEFINED:
            return finalize(result=default)
        msg = f"{error_msg or ''} Timeout {timeout} seconds exceeded".strip()
        raise TimeoutError(msg) from e

    except Exception as e:
        if error_map is not None:
            handler = error_map.get(type(e))
            if handler:
                handler(e)
                return finalize(None)

        if default is not UNDEFINED:
            return finalize(default)

        msg = (
            f"{error_msg} Error: {e}"
            if error_msg
            else f"An error occurred in async execution: {e}"
        )
        raise RuntimeError(msg) from e


class TCallParams(CallParams):
    func: Any = None
    timeout: float | None = None
    default: Any = UNDEFINED
    timing: bool = False
    error_msg: str = ""
    initial_delay: float = 0
    error_map: dict = None

    async def __call__(self, func=None):
        if self.func is None and func is None:
            raise ValueError("a sync/async func must be provided")
        return await tcall(
            func or self.func,
            *self.args,
            timeout=self.timeout,
            default=self.default,
            timing=self.timing,
            error_msg=self.error_msg,
            initial_delay=self.initial_delay,
            error_map=self.error_map,
            **self.kwargs,
        )


# --- Path and File Operations ---


def create_path(
    directory: Path | str,
    filename: str,
    extension: str = None,
    timestamp: bool = False,
    dir_exist_ok: bool = True,
    file_exist_ok: bool = False,
    time_prefix: bool = False,
    timestamp_format: str | None = None,
    random_hash_digits: int = 0,
) -> Path:
    """
    Generate a new file path with optional timestamp and a random suffix.

    Args:
        directory: The directory where the file will be created.
        filename: The base name of the file to create.
        extension: The file extension, if not part of filename.
        timestamp: If True, add a timestamp to the filename.
        dir_exist_ok: If True, don't error if directory exists.
        file_exist_ok: If True, allow overwriting existing files.
        time_prefix: If True, timestamp is prefixed instead of suffixed.
        timestamp_format: Custom format for timestamp (default: "%Y%m%d%H%M%S").
        random_hash_digits: Number of hex digits for a random suffix.

    Returns:
        The full Path to the new or existing file.

    Raises:
        ValueError: If no extension or filename invalid.
        FileExistsError: If file exists and file_exist_ok=False.
    """
    if "/" in filename or "\\" in filename:
        raise ValueError("Filename cannot contain directory separators.")

    directory = Path(directory)

    # Extract name and extension from filename if present
    if "." in filename:
        name, ext = filename.rsplit(".", 1)
    else:
        name, ext = filename, extension

    if not ext:
        raise ValueError("No extension provided for filename.")

    # Ensure extension has a single leading dot
    ext = f".{ext.lstrip('.')}" if ext else ""

    # Add timestamp if requested
    if timestamp:
        ts_str = datetime.now().strftime(timestamp_format or "%Y%m%d%H%M%S")
        name = f"{ts_str}_{name}" if time_prefix else f"{name}_{ts_str}"

    # Add random suffix if requested
    if random_hash_digits > 0:
        # Use UUID4 and truncate its hex for random suffix
        random_suffix = uuid.uuid4().hex[:random_hash_digits]
        name = f"{name}-{random_suffix}"

    full_path = directory / f"{name}{ext}"

    # Check if file or directory existence
    full_path.parent.mkdir(parents=True, exist_ok=dir_exist_ok)
    if full_path.exists() and not file_exist_ok:
        raise FileExistsError(
            f"File {full_path} already exists and file_exist_ok is False."
        )

    return full_path


class CreatePathParams(Params):
    directory: Path | str
    filename: str
    extension: str = None
    timestamp: bool = False
    dir_exist_ok: bool = True
    file_exist_ok: bool = False
    time_prefix: bool = False
    timestamp_format: str | None = None
    random_hash_digits: int = 0

    def __call__(
        self, directory: Path | str = None, filename: str = None
    ) -> Path:
        return create_path(
            directory or self.directory,
            filename or self.filename,
            extension=self.extension,
            timestamp=self.timestamp,
            dir_exist_ok=self.dir_exist_ok,
            file_exist_ok=self.file_exist_ok,
            time_prefix=self.time_prefix,
            timestamp_format=self.timestamp_format,
            random_hash_digits=self.random_hash_digits,
        )


# --- JSON and XML Conversion ---


def to_xml(
    obj: dict | list | str | int | float | bool | None,
    root_name: str = "root",
) -> str:
    """
    Convert a dictionary into an XML formatted string.

    Rules:
    - A dictionary key becomes an XML tag.
    - If the dictionary value is:
      - A primitive type (str, int, float, bool, None): it becomes the text content of the tag.
      - A list: each element of the list will repeat the same tag.
      - Another dictionary: it is recursively converted to nested XML.
    - root_name sets the top-level XML element name.

    Args:
        obj: The Python object to convert (typically a dictionary).
        root_name: The name of the root XML element.

    Returns:
        A string representing the XML.

    Examples:
        >>> to_xml({"a": 1, "b": {"c": "hello", "d": [10, 20]}}, root_name="data")
        '<data><a>1</a><b><c>hello</c><d>10</d><d>20</d></b></data>'
    """

    def _convert(value: Any, tag_name: str) -> str:
        # If value is a dict, recursively convert its keys
        if isinstance(value, dict):
            inner = "".join(_convert(v, k) for k, v in value.items())
            return f"<{tag_name}>{inner}</{tag_name}>"
        # If value is a list, repeat the same tag for each element
        elif isinstance(value, list):
            return "".join(_convert(item, tag_name) for item in value)
        # If value is a primitive, convert to string and place inside tag
        else:
            text = "" if value is None else str(value)
            # Escape special XML characters if needed (minimal)
            text = (
                text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;")
            )
            return f"<{tag_name}>{text}</{tag_name}>"

    # If top-level obj is not a dict, wrap it in one
    if not isinstance(obj, dict):
        obj = {root_name: obj}

    inner_xml = "".join(_convert(v, k) for k, v in obj.items())
    return f"<{root_name}>{inner_xml}</{root_name}>"


def fuzzy_parse_json(
    str_to_parse: str, /
) -> dict[str, Any] | list[dict[str, Any]]:
    """
    Attempt to parse a JSON string, trying a few minimal "fuzzy" fixes if needed.

    Steps:
    1. Parse directly with json.loads.
    2. Replace single quotes with double quotes, normalize spacing, and try again.
    3. Attempt to fix unmatched brackets using fix_json_string.
    4. If all fail, raise ValueError.

    Args:
        str_to_parse: The JSON string to parse

    Returns:
        Parsed JSON (dict or list of dicts)

    Raises:
        ValueError: If the string cannot be parsed as valid JSON
        TypeError: If the input is not a string
    """
    _check_valid_str(str_to_parse)

    # 1. Direct attempt
    with contextlib.suppress(Exception):
        return json.loads(str_to_parse)

    # 2. Try cleaning: replace single quotes with double and normalize
    cleaned = _clean_json_string(str_to_parse.replace("'", '"'))
    with contextlib.suppress(Exception):
        return json.loads(cleaned)

    # 3. Try fixing brackets
    fixed = fix_json_string(cleaned)
    with contextlib.suppress(Exception):
        return json.loads(fixed)

    # If all attempts fail
    raise ValueError("Invalid JSON string")


def _check_valid_str(str_to_parse: str, /):
    if not isinstance(str_to_parse, str):
        raise TypeError("Input must be a string")
    if not str_to_parse.strip():
        raise ValueError("Input string is empty")


def _clean_json_string(s: str) -> str:
    """Basic normalization: replace unescaped single quotes, trim spaces, ensure keys are quoted."""
    # Replace unescaped single quotes with double quotes
    # '(?<!\\)'" means a single quote not preceded by a backslash
    s = re.sub(r"(?<!\\)'", '"', s)
    # Collapse multiple whitespaces
    s = re.sub(r"\s+", " ", s)
    # Ensure keys are quoted
    # This attempts to find patterns like { key: value } and turn them into {"key": value}
    s = re.sub(r'([{,])\s*([^"\s]+)\s*:', r'\1"\2":', s)
    return s.strip()


def fix_json_string(str_to_parse: str, /) -> str:
    """Try to fix JSON string by ensuring brackets are matched properly."""
    if not str_to_parse:
        raise ValueError("Input string is empty")

    brackets = {"{": "}", "[": "]"}
    open_brackets = []
    pos = 0
    length = len(str_to_parse)

    while pos < length:
        char = str_to_parse[pos]

        if char == "\\":
            pos += 2  # Skip escaped chars
            continue

        if char == '"':
            pos += 1
            # skip string content
            while pos < length:
                if str_to_parse[pos] == "\\":
                    pos += 2
                    continue
                if str_to_parse[pos] == '"':
                    pos += 1
                    break
                pos += 1
            continue

        if char in brackets:
            open_brackets.append(brackets[char])
        elif char in brackets.values():
            if not open_brackets:
                # Extra closing bracket
                # Better to raise error than guess
                raise ValueError("Extra closing bracket found.")
            if open_brackets[-1] != char:
                # Mismatched bracket
                raise ValueError("Mismatched brackets.")
            open_brackets.pop()

        pos += 1

    # Add missing closing brackets if any
    if open_brackets:
        str_to_parse += "".join(reversed(open_brackets))

    return str_to_parse


@overload
def to_dict(
    input_: Any,
    /,
    *,
    use_model_dump: bool = True,
    fuzzy_parse: bool = False,
    suppress: bool = False,
    str_type: Literal["json", "xml"] | None = "json",
    parser: Callable[[str], Any] | None = None,
    recursive: Literal[False] = False,
    max_recursive_depth: int | None = None,
    recursive_python_only: bool = True,
    use_enum_values: bool = False,
    remove_root: bool = False,
    root_tag: str = "root",
) -> dict[str, Any]: ...


@overload
def to_dict(
    input_: Any,
    /,
    *,
    use_model_dump: bool = True,
    fuzzy_parse: bool = False,
    suppress: bool = False,
    str_type: Literal["json", "xml"] | None = "json",
    parser: Callable[[str], Any] | None = None,
    recursive: Literal[True],
    max_recursive_depth: int | None = None,
    recursive_python_only: bool = True,
    use_enum_values: bool = False,
    remove_root: bool = False,
    root_tag: str = "root",
) -> Any: ...


def to_dict(
    input_: Any,
    /,
    *,
    use_model_dump: bool = True,
    fuzzy_parse: bool = False,
    suppress: bool = False,
    str_type: Literal["json", "xml"] | None = "json",
    parser: Callable[[str], Any] | None = None,
    recursive: bool = False,
    max_recursive_depth: int | None = None,
    recursive_python_only: bool = True,
    use_enum_values: bool = False,
    remove_root: bool = False,
    root_tag: str = "root",
) -> Any:
    try:
        if recursive:
            return recursive_to_dict(
                input_,
                use_model_dump=use_model_dump,
                fuzzy_parse=fuzzy_parse,
                str_type=str_type,
                parser=parser,
                max_recursive_depth=max_recursive_depth,
                recursive_python_only=recursive_python_only,
                use_enum_values=use_enum_values,
                remove_root=remove_root,
                root_tag=root_tag,
            )
        return _to_dict(
            input_,
            fuzzy_parse=fuzzy_parse,
            str_type=str_type,
            parser=parser,
            use_model_dump=use_model_dump,
            use_enum_values=use_enum_values,
            remove_root=remove_root,
            root_tag=root_tag,
        )
    except Exception:
        if suppress:
            return {}
        # Removed `or input_ == ""` so empty string raises ValueError
        raise


def recursive_to_dict(
    input_: Any,
    /,
    *,
    use_model_dump: bool,
    fuzzy_parse: bool,
    str_type: Literal["json", "xml"] | None,
    parser: Callable[[str], Any] | None,
    max_recursive_depth: int | None,
    recursive_python_only: bool,
    use_enum_values: bool,
    remove_root: bool,
    root_tag: str,
) -> Any:
    if max_recursive_depth is None:
        max_recursive_depth = 5
    if max_recursive_depth < 0:
        raise ValueError("max_recursive_depth must be a non-negative integer")
    if max_recursive_depth > 10:
        raise ValueError("max_recursive_depth must be <= 10")

    return _recur_to_dict(
        input_,
        max_recursive_depth=max_recursive_depth,
        current_depth=0,
        recursive_custom_types=not recursive_python_only,
        use_model_dump=use_model_dump,
        fuzzy_parse=fuzzy_parse,
        str_type=str_type,
        parser=parser,
        use_enum_values=use_enum_values,
        remove_root=remove_root,
        root_tag=root_tag,
    )


def _recur_to_dict(
    input_: Any,
    /,
    *,
    max_recursive_depth: int,
    current_depth: int,
    recursive_custom_types: bool,
    use_model_dump: bool,
    fuzzy_parse: bool,
    str_type: Literal["json", "xml"] | None,
    parser: Callable[[str], Any] | None,
    use_enum_values: bool,
    remove_root: bool,
    root_tag: str,
) -> Any:
    if current_depth >= max_recursive_depth:
        return input_

    if isinstance(input_, str):
        try:
            parsed = _to_dict(
                input_,
                fuzzy_parse=fuzzy_parse,
                str_type=str_type,
                parser=parser,
                use_model_dump=use_model_dump,
                use_enum_values=use_enum_values,
                remove_root=remove_root,
                root_tag=root_tag,
            )
            return _recur_to_dict(
                parsed,
                max_recursive_depth=max_recursive_depth,
                current_depth=current_depth + 1,
                recursive_custom_types=recursive_custom_types,
                use_model_dump=use_model_dump,
                fuzzy_parse=fuzzy_parse,
                str_type=str_type,
                parser=parser,
                use_enum_values=use_enum_values,
                remove_root=remove_root,
                root_tag=root_tag,
            )
        except Exception:
            return input_

    elif isinstance(input_, dict):
        return {
            k: _recur_to_dict(
                v,
                max_recursive_depth=max_recursive_depth,
                current_depth=current_depth + 1,
                recursive_custom_types=recursive_custom_types,
                use_model_dump=use_model_dump,
                fuzzy_parse=fuzzy_parse,
                str_type=str_type,
                parser=parser,
                use_enum_values=use_enum_values,
                remove_root=remove_root,
                root_tag=root_tag,
            )
            for k, v in input_.items()
        }

    elif isinstance(input_, (list, tuple, set)):
        processed = [
            _recur_to_dict(
                e,
                max_recursive_depth=max_recursive_depth,
                current_depth=current_depth + 1,
                recursive_custom_types=recursive_custom_types,
                use_model_dump=use_model_dump,
                fuzzy_parse=fuzzy_parse,
                str_type=str_type,
                parser=parser,
                use_enum_values=use_enum_values,
                remove_root=remove_root,
                root_tag=root_tag,
            )
            for e in input_
        ]
        return type(input_)(processed)

    elif isinstance(input_, type) and issubclass(input_, Enum):
        try:
            obj_dict = _to_dict(
                input_,
                fuzzy_parse=fuzzy_parse,
                str_type=str_type,
                parser=parser,
                use_model_dump=use_model_dump,
                use_enum_values=use_enum_values,
                remove_root=remove_root,
                root_tag=root_tag,
            )
            return _recur_to_dict(
                obj_dict,
                max_recursive_depth=max_recursive_depth,
                current_depth=current_depth + 1,
                recursive_custom_types=recursive_custom_types,
                use_model_dump=use_model_dump,
                fuzzy_parse=fuzzy_parse,
                str_type=str_type,
                parser=parser,
                use_enum_values=use_enum_values,
                remove_root=remove_root,
                root_tag=root_tag,
            )
        except Exception:
            return input_

    elif recursive_custom_types:
        try:
            obj_dict = _to_dict(
                input_,
                fuzzy_parse=fuzzy_parse,
                str_type=str_type,
                parser=parser,
                use_model_dump=use_model_dump,
                use_enum_values=use_enum_values,
                remove_root=remove_root,
                root_tag=root_tag,
            )
            return _recur_to_dict(
                obj_dict,
                max_recursive_depth=max_recursive_depth,
                current_depth=current_depth + 1,
                recursive_custom_types=recursive_custom_types,
                use_model_dump=use_model_dump,
                fuzzy_parse=fuzzy_parse,
                str_type=str_type,
                parser=parser,
                use_enum_values=use_enum_values,
                remove_root=remove_root,
                root_tag=root_tag,
            )
        except Exception:
            return input_

    return input_


def _enum_to_dict(input_: type[Enum], /, use_enum_values: bool) -> dict:
    members = dict(input_.__members__)
    return {
        k: (v.value if use_enum_values else v.name) for k, v in members.items()
    }


def _str_to_dict(
    input_: str,
    /,
    *,
    fuzzy_parse: bool,
    str_type: Literal["json", "xml"] | None,
    parser: Callable[[str], Any] | None,
    remove_root: bool,
    root_tag: str,
) -> dict[str, Any]:
    if parser:
        return parser(input_)

    if str_type == "xml":
        # Wrap in try-except to raise ValueError on parse errors
        try:
            import xmltodict  # type: ignore

            parsed = xmltodict.parse(input_)
        except ImportError as e:
            raise ImportError(
                "xmltodict is required for XML parsing. Install with: pip install xmltodict"
            )
        except Exception as e:
            raise ValueError(f"Invalid XML: {e}") from e

        if remove_root and isinstance(parsed, dict) and len(parsed) == 1:
            parsed = next(iter(parsed.values()))
            if not isinstance(parsed, dict):
                parsed = {"value": parsed}
        else:
            if root_tag != "root":
                if isinstance(parsed, dict) and len(parsed) == 1:
                    old_root_key = next(iter(parsed.keys()))
                    contents = parsed[old_root_key]
                    parsed = {root_tag: contents}
                else:
                    parsed = {root_tag: parsed}

        if not isinstance(parsed, dict):
            parsed = {"value": parsed}
        return parsed

    # JSON
    if fuzzy_parse:
        return fuzzy_parse_json(input_)
    try:
        return json.loads(input_)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e


def _na_to_dict(input_: Any) -> dict[str, Any]:
    # Handle PydanticUndefinedType specifically
    if input_ is PydanticUndefinedType:
        return {}
    if isinstance(input_, (type(None), UndefinedType, PydanticUndefinedType)):
        return {}
    return {}


def _model_to_dict(
    input_: Any,
    /,
    *,
    use_model_dump: bool,
) -> dict[str, Any]:
    # If input is a BaseModel
    if isinstance(input_, BaseModel):
        if use_model_dump and hasattr(input_, "model_dump"):
            return input_.model_dump()

        methods = ("to_dict", "to_json", "json", "dict", "model_dump")
        for method in methods:
            if hasattr(input_, method):
                result = getattr(input_, method)()
                return (
                    json.loads(result) if isinstance(result, str) else result
                )

        if hasattr(input_, "__dict__"):
            return dict(input_.__dict__)

        try:
            return dict(input_)
        except Exception as e:
            raise ValueError(f"Unable to convert input to dictionary: {e}")
    else:
        # Non-BaseModel objects that reach here
        # Distinguish between Sequence and Iterable
        if isinstance(input_, Sequence) and not isinstance(input_, str):
            # If it's a sequence (like a list), we wouldn't be here,
            # because lists handled in _to_dict before calling _model_to_dict
            pass

        # If it's not a BaseModel and not a Sequence,
        # it might be a generator or custom object
        # Try directly:
        try:
            return dict(input_)
        except TypeError:
            # Not directly dict-able
            # If it's iterable but not a sequence, handle as iterable:
            if isinstance(input_, Iterable) and not isinstance(
                input_, Sequence
            ):
                return _iterable_to_dict(input_)
            raise ValueError("Unable to convert input to dictionary")


def _set_to_dict(input_: set, /) -> dict[str, Any]:
    return {str(v): v for v in input_}


def _iterable_to_dict(input_: Iterable, /) -> dict[str, Any]:
    return {str(idx): v for idx, v in enumerate(input_)}


def _to_dict(
    input_: Any,
    /,
    *,
    fuzzy_parse: bool,
    str_type: Literal["json", "xml"] | None,
    parser: Callable[[str], Any] | None,
    use_model_dump: bool,
    use_enum_values: bool,
    remove_root: bool,
    root_tag: str,
) -> dict[str, Any]:

    if isinstance(input_, set):
        return _set_to_dict(input_)

    if isinstance(input_, type) and issubclass(input_, Enum):
        return _enum_to_dict(input_, use_enum_values=use_enum_values)

    if isinstance(input_, Mapping):
        return dict(input_)

    if input_ is PydanticUndefinedType:
        return {}

    if isinstance(input_, (type(None), UndefinedType, PydanticUndefinedType)):
        return _na_to_dict(input_)

    if isinstance(input_, str):
        return _str_to_dict(
            input_,
            fuzzy_parse=fuzzy_parse,
            str_type=str_type,
            parser=parser,
            remove_root=remove_root,
            root_tag=root_tag,
        )

    if isinstance(input_, BaseModel):
        return _model_to_dict(input_, use_model_dump=use_model_dump)

    # If not BaseModel and not a str
    if isinstance(input_, Sequence) and not isinstance(input_, str):
        # Sequence like list/tuple handled already
        # If we get here, it's likely a custom object not handled before
        # We do last fallback:
        try:
            return dict(input_)
        except Exception:
            # If fails, it's not a dict-convertible sequence, treat as iterable:
            return _iterable_to_dict(input_)

    if isinstance(input_, Iterable):
        return _iterable_to_dict(input_)

    # last fallback
    try:
        return dict(input_)
    except Exception as e:
        raise ValueError(f"Unable to convert input to dictionary: {e}")


class ToDictParams(Params):
    use_model_dump: bool = True
    fuzzy_parse: bool = False
    suppress: bool = False
    str_type: Literal["json", "xml"] | None = "json"
    parser: Callable[[str], Any] | None = None
    recursive: bool = False
    max_recursive_depth: int | None = None
    recursive_python_only: bool = True
    use_enum_values: bool = False
    remove_root: bool = False
    root_tag: str = "root"

    def __call__(self, input_, /):
        return to_dict(
            input_,
            use_model_dump=self.use_model_dump,
            fuzzy_parse=self.fuzzy_parse,
            suppress=self.suppress,
            str_type=self.str_type,
            parser=self.parser,
            recursive=self.recursive,
            max_recursive_depth=self.max_recursive_depth,
            recursive_python_only=self.recursive_python_only,
            use_enum_values=self.use_enum_values,
            remove_root=self.remove_root,
            root_tag=self.root_tag,
        )


# Precompile the regex for extracting JSON code blocks
_JSON_BLOCK_PATTERN = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)


def to_json(
    input_data: str | list[str], /, *, fuzzy_parse: bool = False
) -> dict[str, Any] | list[dict[str, Any]]:
    """
    Extract and parse JSON content from a string or markdown code blocks.

    Attempts direct JSON parsing first. If that fails, looks for JSON content
    within markdown code blocks denoted by ```json.

    Args:
        input_data (str | list[str]): The input string or list of strings to parse.
        fuzzy_parse (bool): If True, attempts fuzzy JSON parsing on failed attempts.

    Returns:
        dict or list of dicts:
            - If a single JSON object is found: returns a dict.
            - If multiple JSON objects are found: returns a list of dicts.
            - If no valid JSON found: returns an empty list.
    """

    # If input_data is a list, join into a single string
    if isinstance(input_data, list):
        input_str = "\n".join(input_data)
    else:
        input_str = input_data

    # 1. Try direct parsing
    try:
        if fuzzy_parse:
            return fuzzy_parse_json(input_str)
        return json.loads(input_str)
    except Exception:
        pass

    # 2. Attempt extracting JSON blocks from markdown
    matches = _JSON_BLOCK_PATTERN.findall(input_str)
    if not matches:
        return []

    # If only one match, return single dict; if multiple, return list of dicts
    if len(matches) == 1:
        data_str = matches[0]
        return (
            fuzzy_parse_json(data_str) if fuzzy_parse else json.loads(data_str)
        )

    # Multiple matches
    if fuzzy_parse:
        return [fuzzy_parse_json(m) for m in matches]
    else:
        return [json.loads(m) for m in matches]
