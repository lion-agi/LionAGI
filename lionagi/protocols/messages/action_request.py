from collections.abc import Callable
from typing import Any, ClassVar

from typing_extensions import override

from lionagi.libs.parse import to_dict
from lionagi.utils import copy

from ..base import ID
from .message import MessageFlag, MessageRole, RoledMessage, Template, env


def prepare_action_request(
    function: str | Callable,
    arguments: dict,
) -> dict:
    args = copy(arguments)
    if not isinstance(arguments, dict):
        try:
            arguments = to_dict(
                args, fuzzy_parse=True, str_type="json", suppress=True
            )
            if not arguments:
                arguments = to_dict(args, str_type="xml", suppress=True)
            if not arguments or not isinstance(arguments, dict):
                raise ValueError
        except Exception:
            raise ValueError("Arguments must be a dictionary.")
    return {"action_request": {"function": function, "arguments": arguments}}


class ActionRequest(RoledMessage):
    """
    Represents a request for an action in the system.

    This class encapsulates the details needed to execute a function call,
    including the function name/reference and its arguments. It also tracks
    whether the request has been responded to.

    Example:
        >>> request = ActionRequest(
        ...     function="calculate_sum",
        ...     arguments={"numbers": [1, 2, 3]},
        ...     sender="user",
        ...     recipient="system"
        ... )
        >>> print(request.function)
        'calculate_sum'
    """

    template: ClassVar[Template] = env.get_template("action_request.jinja2")

    @override
    def __init__(
        self,
        function: str | Callable | MessageFlag,
        arguments: dict | MessageFlag,
        sender: ID.Ref | MessageFlag = None,
        recipient: ID.Ref | MessageFlag = None,
        protected_init_params: dict | None = None,
    ) -> None:
        """
        Initialize an ActionRequest instance.

        Args:
            function: The function to be invoked
            arguments: The arguments for the function
            sender: The sender of the request
            recipient: The recipient of the request
            protected_init_params: Protected initialization parameters
        """
        message_flags = [function, arguments, sender, recipient]

        if all(x == MessageFlag.MESSAGE_LOAD for x in message_flags):
            protected_init_params = protected_init_params or {}
            super().__init__(**protected_init_params)
            return

        if all(x == MessageFlag.MESSAGE_CLONE for x in message_flags):
            super().__init__(role=MessageRole.ASSISTANT)
            return

        function = function.__name__ if callable(function) else function

        super().__init__(
            role=MessageRole.ASSISTANT,
            content=prepare_action_request(
                function=function, arguments=arguments
            ),
            sender=sender,
            recipient=recipient,
        )

    @property
    def action_response_id(self) -> str | None:
        """
        Get the ID of the corresponding action response.

        Returns:
            LnID | None: The ID of the action response, or None if not responded
        """
        return self.content.get("action_response_id", None)

    @property
    def is_responded(self) -> bool:
        """
        Check if the action request has been responded to.

        Returns:
            bool: True if the request has a response, False otherwise
        """
        return self.action_response_id is not None

    @property
    def request(self) -> dict[str, Any]:
        """
        Get the action request content as a dictionary.

        Returns:
            dict[str, Any]: The request content excluding output
        """
        a = copy(self.content.get("action_request", {}))
        a.pop("output", None)
        return a

    @property
    def rendered(self) -> str:
        """
        Get the rendered content of the action request.

        Returns:
            str: The rendered content of the request
        """
        return self.template.render(self.request)

    @property
    def arguments(self) -> dict[str, Any]:
        """
        Get the arguments for the action request.

        Returns:
            dict[str, Any]: The arguments dictionary
        """
        return self.request.get("arguments", {})

    @property
    def function(self) -> str:
        """
        Get the function name for the action request.

        Returns:
            str: The name of the function to be invoked
        """
        return self.request.get("function", "")

    @override
    def _format_content(self) -> dict[str, Any]:
        return {"role": self.role.value, "content": self.rendered}
