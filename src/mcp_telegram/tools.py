from __future__ import annotations

import logging
import sys
import typing as t
from functools import singledispatch

from mcp.types import (
    EmbeddedResource,
    ImageContent,
    TextContent,
    Tool,
)
from pydantic import BaseModel, ConfigDict
from telethon import TelegramClient, custom, functions, types  # type: ignore[import-untyped]

from .telegram import create_client

logger = logging.getLogger(__name__)


# How to add a new tool:
#
# 1. Create a new class that inherits from ToolArgs
#    ```python
#    class NewTool(ToolArgs):
#        """Description of the new tool."""
#        pass
#    ```
#    Attributes of the class will be used as arguments for the tool.
#    The class docstring will be used as the tool description.
#
# 2. Implement the tool_runner function for the new class
#    ```python
#    @tool_runner.register
#    async def new_tool(args: NewTool) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
#        pass
#    ```
#    The function should return a sequence of TextContent, ImageContent or EmbeddedResource.
#    The function should be async and accept a single argument of the new class.
#
# 3. Done! Restart the client and the new tool should be available.


class ToolArgs(BaseModel):
    model_config = ConfigDict()


@singledispatch
async def tool_runner(
    args,  # noqa: ANN001
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    raise NotImplementedError(f"Unsupported type: {type(args)}")


def tool_description(args: type[ToolArgs]) -> Tool:
    return Tool(
        name=args.__name__,
        description=args.__doc__,
        inputSchema=args.model_json_schema(),
    )


def tool_args(tool: Tool, *args, **kwargs) -> ToolArgs:  # noqa: ANN002, ANN003
    return sys.modules[__name__].__dict__[tool.name](*args, **kwargs)


### ListDialogs ###


class ListDialogs(ToolArgs):
    """List available dialogs, chats and channels."""

    unread: bool = False
    archived: bool = False
    ignore_pinned: bool = False


@tool_runner.register
async def list_dialogs(
    args: ListDialogs,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[ListDialogs] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        dialog: custom.dialog.Dialog
        async for dialog in client.iter_dialogs(archived=args.archived, ignore_pinned=args.ignore_pinned):
            if args.unread and dialog.unread_count == 0:
                continue
            msg = (
                f"name='{dialog.name}' id={dialog.id} "
                f"unread={dialog.unread_count} mentions={dialog.unread_mentions_count}"
            )
            response.append(TextContent(type="text", text=msg))

    return response


### SendMessage ###


class SendMessage(ToolArgs):
    """
    Send a message to a specified dialog, chat, or channel.
    
    Allows sending text messages to a specified chat identified by its dialog_id.
    The message will be sent as plain text.
    """

    dialog_id: int
    message: str


@tool_runner.register
async def send_message(
    args: SendMessage,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[SendMessage] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            message = await client.send_message(args.dialog_id, args.message)
            response.append(TextContent(type="text", text=f"Message sent successfully. Message ID: {message.id}"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to send message: {str(e)}"))

    return response


### DeleteMessage ###


class DeleteMessage(ToolArgs):
    """
    Delete a specific message from a dialog, chat, or channel.
    
    Requires both the dialog_id and the specific message_id to delete.
    """

    dialog_id: int
    message_id: int


@tool_runner.register
async def delete_message(
    args: DeleteMessage,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[DeleteMessage] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            await client.delete_messages(args.dialog_id, args.message_id)
            response.append(TextContent(type="text", text=f"Successfully deleted message {args.message_id}"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to delete message: {str(e)}"))

    return response


### EditMessage ###


class EditMessage(ToolArgs):
    """
    Edit an existing message in a dialog, chat, or channel.
    
    Requires the dialog_id, message_id, and the new text to replace the original message.
    """

    dialog_id: int
    message_id: int
    new_text: str


@tool_runner.register
async def edit_message(
    args: EditMessage,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[EditMessage] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            await client.edit_message(args.dialog_id, args.message_id, text=args.new_text)
            response.append(TextContent(type="text", text=f"Successfully edited message {args.message_id}"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to edit message: {str(e)}"))

    return response


### ListMessages ###


class ListMessages(ToolArgs):
    """
    List messages in a given dialog, chat or channel. The messages are listed in order from newest to oldest.

    If `unread` is set to `True`, only unread messages will be listed. Once a message is read, it will not be
    listed again.

    If `limit` is set, only the last `limit` messages will be listed. If `unread` is set, the limit will be
    the minimum between the unread messages and the limit.
    """

    dialog_id: int
    unread: bool = False
    limit: int = 100


@tool_runner.register
async def list_messages(
    args: ListMessages,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[ListMessages] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        result = await client(functions.messages.GetPeerDialogsRequest(peers=[args.dialog_id]))
        if not result:
            raise ValueError(f"Channel not found: {args.dialog_id}")

        if not isinstance(result, types.messages.PeerDialogs):
            raise TypeError(f"Unexpected result: {type(result)}")

        for dialog in result.dialogs:
            logger.debug("dialog: %s", dialog)
        for message in result.messages:
            logger.debug("message: %s", message)

        iter_messages_args: dict[str, t.Any] = {
            "entity": args.dialog_id,
            "reverse": False,
        }
        if args.unread:
            iter_messages_args["limit"] = min(dialog.unread_count, args.limit)
        else:
            iter_messages_args["limit"] = args.limit

        logger.debug("iter_messages_args: %s", iter_messages_args)
        async for message in client.iter_messages(**iter_messages_args):
            logger.debug("message: %s", type(message))
            if isinstance(message, custom.Message) and message.text:
                logger.debug("message: %s", message.text)
                response.append(TextContent(type="text", text=message.text))

    return response
