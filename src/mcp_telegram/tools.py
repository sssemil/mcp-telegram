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


### ForwardMessage ###


class ForwardMessage(ToolArgs):
    """
    Forward a message from one chat to another.
    
    Requires the source chat ID, message ID to forward, and the destination chat ID.
    Optionally, you can disable notification for the forwarded message.
    """

    from_dialog_id: int
    message_id: int
    to_dialog_id: int
    silent: bool = False


@tool_runner.register
async def forward_message(
    args: ForwardMessage,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[ForwardMessage] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            message = await client.forward_messages(
                entity=args.to_dialog_id,
                messages=args.message_id,
                from_peer=args.from_dialog_id,
                silent=args.silent
            )
            response.append(TextContent(type="text", 
                text=f"Message forwarded successfully. New message ID: {message.id}"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to forward message: {str(e)}"))

    return response


### PinMessage ###


class PinMessage(ToolArgs):
    """
    Pin a message in a chat.
    
    Requires the chat ID and message ID to pin.
    Optionally, you can disable notification for the pinned message
    and pin the message silently.
    """

    dialog_id: int
    message_id: int
    notify: bool = True
    pm_oneside: bool = False  # For private chats, pin only for the user


@tool_runner.register
async def pin_message(
    args: PinMessage,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[PinMessage] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            await client.pin_message(
                entity=args.dialog_id,
                message=args.message_id,
                notify=args.notify,
                pm_oneside=args.pm_oneside
            )
            response.append(TextContent(type="text", text=f"Successfully pinned message {args.message_id}"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to pin message: {str(e)}"))

    return response


### UnpinMessage ###


class UnpinMessage(ToolArgs):
    """
    Unpin a message from a chat.
    
    Requires the chat ID and optionally the specific message ID to unpin.
    If no message ID is provided, all pinned messages will be unpinned.
    """

    dialog_id: int
    message_id: int | None = None  # If None, unpin all messages


@tool_runner.register
async def unpin_message(
    args: UnpinMessage,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[UnpinMessage] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            await client.unpin_message(
                entity=args.dialog_id,
                message=args.message_id
            )
            msg = "Successfully unpinned all messages" if args.message_id is None else f"Successfully unpinned message {args.message_id}"
            response.append(TextContent(type="text", text=msg))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to unpin message(s): {str(e)}"))

    return response


### GetMessageReactions ###


class GetMessageReactions(ToolArgs):
    """
    Get all reactions for a specific message.
    
    Returns a list of reactions and the count of each reaction on the message.
    """

    dialog_id: int
    message_id: int


@tool_runner.register
async def get_message_reactions(
    args: GetMessageReactions,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[GetMessageReactions] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            message = await client.get_messages(args.dialog_id, ids=args.message_id)
            if not message:
                response.append(TextContent(type="text", text="Message not found"))
                return response
            
            if not hasattr(message, 'reactions') or not message.reactions:
                response.append(TextContent(type="text", text="No reactions on this message"))
                return response
            
            reaction_list = []
            for reaction in message.reactions.results:
                count = reaction.count
                reaction_data = reaction.reaction
                if hasattr(reaction_data, 'emoticon'):
                    reaction_list.append(f"{reaction_data.emoticon}: {count}")
                elif hasattr(reaction_data, 'custom_emoji_id'):
                    reaction_list.append(f"Custom emoji {reaction_data.custom_emoji_id}: {count}")
            
            response.append(TextContent(type="text", text="Reactions on message:\n" + "\n".join(reaction_list)))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to get message reactions: {str(e)}"))

    return response


### ReactToMessage ###


class ReactToMessage(ToolArgs):
    """
    Add or remove a reaction to/from a message.
    
    You can react with either an emoji or a custom emoji ID.
    Set add_reaction to False to remove the reaction instead of adding it.
    """

    dialog_id: int
    message_id: int
    emoji: str  # Can be either an emoji or a custom emoji ID
    add_reaction: bool = True  # True to add reaction, False to remove
    big: bool = False  # True to send a big reaction


@tool_runner.register
async def react_to_message(
    args: ReactToMessage,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[ReactToMessage] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            # Creating the reaction object
            from telethon.tl.types import ReactionEmoji, ReactionCustomEmoji
            
            # Check if it's a custom emoji ID (numeric string) or regular emoji
            if args.emoji.isdigit():
                reaction = ReactionCustomEmoji(custom_emoji_id=int(args.emoji))
            else:
                reaction = ReactionEmoji(emoticon=args.emoji)
            
            await client.send_reaction(
                entity=args.dialog_id,
                message=args.message_id,
                reaction=reaction if args.add_reaction else None,
                big=args.big
            )
            
            action = "added to" if args.add_reaction else "removed from"
            response.append(TextContent(type="text", 
                text=f"Reaction {args.emoji} successfully {action} message {args.message_id}"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to handle reaction: {str(e)}"))

    return response


### ReplyToMessage ###


class ReplyToMessage(ToolArgs):
    """
    Reply to a specific message in a chat.
    
    Creates a new message that is a reply to the specified message.
    You can optionally send the reply silently (without notification).
    """

    dialog_id: int
    message_id: int  # The message to reply to
    text: str  # The reply text
    silent: bool = False  # Send silently (no notification)


@tool_runner.register
async def reply_to_message(
    args: ReplyToMessage,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[ReplyToMessage] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            message = await client.send_message(
                entity=args.dialog_id,
                message=args.text,
                reply_to=args.message_id,
                silent=args.silent
            )
            response.append(TextContent(type="text", 
                text=f"Reply sent successfully. New message ID: {message.id}"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to send reply: {str(e)}"))

    return response


### SendPhoto ###


class SendPhoto(ToolArgs):
    """
    Send a photo to a chat.
    
    Accepts a local file path or URL to the image.
    You can optionally include a caption and send it silently.
    """

    dialog_id: int
    photo_path: str  # Local file path or URL
    caption: str | None = None
    silent: bool = False
    reply_to: int | None = None  # Optional message ID to reply to


@tool_runner.register
async def send_photo(
    args: SendPhoto,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[SendPhoto] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            message = await client.send_file(
                entity=args.dialog_id,
                file=args.photo_path,
                caption=args.caption,
                silent=args.silent,
                reply_to=args.reply_to,
                force_document=False
            )
            response.append(TextContent(type="text", 
                text=f"Photo sent successfully. Message ID: {message.id}"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to send photo: {str(e)}"))

    return response


### SendDocument ###


class SendDocument(ToolArgs):
    """
    Send a document/file to a chat.
    
    Accepts a local file path or URL.
    You can optionally include a caption and send it silently.
    The file will be sent as a document, preserving its original format.
    """

    dialog_id: int
    file_path: str  # Local file path or URL
    caption: str | None = None
    silent: bool = False
    reply_to: int | None = None  # Optional message ID to reply to
    thumbnail: str | None = None  # Optional thumbnail image path


@tool_runner.register
async def send_document(
    args: SendDocument,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[SendDocument] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            message = await client.send_file(
                entity=args.dialog_id,
                file=args.file_path,
                caption=args.caption,
                silent=args.silent,
                reply_to=args.reply_to,
                thumb=args.thumbnail,
                force_document=True
            )
            response.append(TextContent(type="text", 
                text=f"Document sent successfully. Message ID: {message.id}"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to send document: {str(e)}"))

    return response


### SendVoice ###


class SendVoice(ToolArgs):
    """
    Send a voice message to a chat.
    
    Accepts a local file path or URL to an audio file.
    The file will be sent as a voice message (round message format).
    Supports common audio formats like mp3, ogg, m4a.
    """

    dialog_id: int
    voice_path: str  # Local file path or URL to audio file
    caption: str | None = None
    silent: bool = False
    reply_to: int | None = None  # Optional message ID to reply to


@tool_runner.register
async def send_voice(
    args: SendVoice,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[SendVoice] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            # Import here to avoid issues with type checking
            from telethon.tl.types import InputMediaUploadedDocument
            from telethon.tl.types import DocumentAttributeAudio
            
            message = await client.send_file(
                entity=args.dialog_id,
                file=args.voice_path,
                voice_note=True,  # This makes it appear as a voice message
                caption=args.caption,
                silent=args.silent,
                reply_to=args.reply_to,
                attributes=[DocumentAttributeAudio(
                    duration=0,  # Duration will be calculated automatically
                    voice=True  # This marks it as a voice message
                )]
            )
            response.append(TextContent(type="text", 
                text=f"Voice message sent successfully. Message ID: {message.id}"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to send voice message: {str(e)}"))

    return response


### SendVideo ###


class SendVideo(ToolArgs):
    """
    Send a video to a chat.
    
    Accepts a local file path or URL to a video file.
    You can optionally include a caption, thumbnail, and other video-specific attributes.
    """

    dialog_id: int
    video_path: str  # Local file path or URL to video file
    caption: str | None = None
    thumbnail: str | None = None  # Optional thumbnail image path
    duration: int | None = None  # Duration in seconds
    width: int | None = None  # Video width
    height: int | None = None  # Video height
    supports_streaming: bool = True
    silent: bool = False
    reply_to: int | None = None  # Optional message ID to reply to


@tool_runner.register
async def send_video(
    args: SendVideo,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[SendVideo] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            # Import here to avoid issues with type checking
            from telethon.tl.types import DocumentAttributeVideo
            
            # Prepare video attributes
            video_attributes = []
            if any([args.duration, args.width, args.height, args.supports_streaming]):
                video_attributes.append(DocumentAttributeVideo(
                    duration=args.duration or 0,
                    w=args.width or 0,
                    h=args.height or 0,
                    supports_streaming=args.supports_streaming
                ))
            
            message = await client.send_file(
                entity=args.dialog_id,
                file=args.video_path,
                caption=args.caption,
                thumb=args.thumbnail,
                attributes=video_attributes if video_attributes else None,
                silent=args.silent,
                reply_to=args.reply_to
            )
            response.append(TextContent(type="text", 
                text=f"Video sent successfully. Message ID: {message.id}"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to send video: {str(e)}"))

    return response


### DownloadMedia ###


class DownloadMedia(ToolArgs):
    """
    Download media from a message.
    
    Downloads the media attachment from a specific message and saves it to a specified path.
    If no path is provided, the file will be saved with its original name in the current directory.
    """

    dialog_id: int
    message_id: int
    output_path: str | None = None  # If None, saves in current directory with original filename
    force_document: bool = False  # If True, will download as document even if it's a photo/video


@tool_runner.register
async def download_media(
    args: DownloadMedia,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[DownloadMedia] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            # Get the message first
            message = await client.get_messages(args.dialog_id, ids=args.message_id)
            if not message or not message.media:
                response.append(TextContent(type="text", 
                    text="No media found in the specified message"))
                return response

            # Download the media
            path = await message.download_media(
                file=args.output_path,
                force_document=args.force_document
            )
            
            if path:
                response.append(TextContent(type="text", 
                    text=f"Media downloaded successfully to: {path}"))
            else:
                response.append(TextContent(type="text", 
                    text="Failed to download media: no path returned"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to download media: {str(e)}"))

    return response


### SendSticker ###


class SendSticker(ToolArgs):
    """
    Send a sticker to a chat.
    
    Accepts either a sticker file path or a sticker ID from a sticker set.
    For animated stickers, make sure the file is in .tgs format.
    For video stickers, make sure the file is in .webm format.
    """

    dialog_id: int
    sticker_path: str  # Local path to sticker file or sticker ID
    reply_to: int | None = None  # Optional message ID to reply to
    silent: bool = False


@tool_runner.register
async def send_sticker(
    args: SendSticker,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[SendSticker] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            # Check if input is a file path or sticker ID
            if args.sticker_path.isdigit():
                # It's a sticker ID, need to get the actual sticker first
                from telethon.tl.types import InputDocument
                sticker = InputDocument(
                    id=int(args.sticker_path),
                    access_hash=0,  # This will be filled by Telethon
                    file_reference=b''  # This will be filled by Telethon
                )
            else:
                # It's a file path
                sticker = args.sticker_path

            message = await client.send_file(
                entity=args.dialog_id,
                file=sticker,
                silent=args.silent,
                reply_to=args.reply_to,
                attributes=[DocumentAttributeSticker(
                    alt="🔥",  # Default emoji
                    stickerset=None  # Not part of a set
                )]
            )
            response.append(TextContent(type="text", 
                text=f"Sticker sent successfully. Message ID: {message.id}"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to send sticker: {str(e)}"))

    return response


### SendGIF ###


class SendGIF(ToolArgs):
    """
    Send a GIF to a chat.
    
    Accepts a local file path or URL to a GIF file.
    The file will be sent as an animated GIF (video note in Telegram).
    """

    dialog_id: int
    gif_path: str  # Local file path or URL to GIF
    caption: str | None = None
    reply_to: int | None = None
    silent: bool = False


@tool_runner.register
async def send_gif(
    args: SendGIF,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[SendGIF] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            from telethon.tl.types import DocumentAttributeAnimated
            
            message = await client.send_file(
                entity=args.dialog_id,
                file=args.gif_path,
                caption=args.caption,
                silent=args.silent,
                reply_to=args.reply_to,
                attributes=[DocumentAttributeAnimated()]  # This marks it as a GIF
            )
            response.append(TextContent(type="text", 
                text=f"GIF sent successfully. Message ID: {message.id}"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to send GIF: {str(e)}"))

    return response


### UploadMedia ###


class UploadMedia(ToolArgs):
    """
    Upload media to Telegram servers without sending it to any chat.
    
    This is useful when you need to reuse the same media file multiple times,
    as it prevents uploading the same file repeatedly.
    Returns the file ID that can be used in other operations.
    """

    file_path: str  # Local path to the file
    file_name: str | None = None  # Optional custom name for the file
    progress_callback: bool = True  # Whether to show upload progress


@tool_runner.register
async def upload_media(
    args: UploadMedia,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[UploadMedia] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            # Define progress callback if requested
            async def progress_callback(current, total):
                percentage = (current / total) * 100
                if percentage % 10 == 0:  # Update every 10%
                    logger.info(f"Upload progress: {percentage:.1f}%")

            file = await client.upload_file(
                file=args.file_path,
                file_name=args.file_name,
                progress_callback=progress_callback if args.progress_callback else None
            )
            
            response.append(TextContent(type="text", 
                text=f"File uploaded successfully. File ID: {file.id}"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to upload file: {str(e)}"))

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
