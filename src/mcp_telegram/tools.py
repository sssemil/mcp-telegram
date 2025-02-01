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


### CreateGroup ###


class CreateGroup(ToolArgs):
    """
    Create a new Telegram group.
    
    Creates a new group with specified title and optional description.
    You can make it a supergroup (recommended for larger groups) and add users immediately.
    """

    title: str
    users: list[str | int] = []  # List of usernames or user IDs to add
    about: str | None = None  # Group description
    supergroup: bool = True  # Whether to create a supergroup
    ttl_period: int | None = None  # Optional message auto-delete time in seconds


@tool_runner.register
async def create_group(
    args: CreateGroup,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[CreateGroup] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            # Create the group
            group = await client.create_group(
                title=args.title,
                users=args.users
            )

            if args.supergroup:
                # Convert to supergroup if requested
                await client(functions.messages.MigrateChat(
                    chat_id=group.chat_id
                ))
                # Get the new supergroup
                group = await client.get_entity(group.id)

            if args.about:
                # Set the group description
                await client(functions.messages.EditChatAbout(
                    peer=group,
                    about=args.about
                ))

            if args.ttl_period:
                # Set message auto-delete timer
                await client(functions.messages.SetHistoryTTL(
                    peer=group,
                    period=args.ttl_period
                ))

            response.append(TextContent(type="text", 
                text=f"Group '{args.title}' created successfully. ID: {group.id}"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to create group: {str(e)}"))

    return response


### CreateChannel ###


class CreateChannel(ToolArgs):
    """
    Create a new Telegram channel.
    
    Creates a broadcast channel with specified title and optional description.
    You can make it private and add users immediately.
    """

    title: str
    about: str | None = None  # Channel description
    private: bool = False  # Whether the channel should be private
    users: list[str | int] = []  # List of usernames or user IDs to add as admins
    ttl_period: int | None = None  # Optional message auto-delete time in seconds


@tool_runner.register
async def create_channel(
    args: CreateChannel,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[CreateChannel] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            # Create the channel
            result = await client(functions.channels.CreateChannel(
                title=args.title,
                about=args.about or "",
                megagroup=False,  # False for channel, True for supergroup
                broadcast=True,  # True for channel
                for_import=False
            ))

            channel = result.chats[0]

            # Add users as admins if specified
            for user in args.users:
                try:
                    user_entity = await client.get_entity(user)
                    await client(functions.channels.EditAdmin(
                        channel=channel,
                        user_id=user_entity,
                        admin_rights=types.ChatAdminRights(
                            post_messages=True,
                            edit_messages=True,
                            delete_messages=True,
                            invite_users=True,
                            change_info=True,
                        ),
                        rank="Admin"
                    ))
                except Exception as e:
                    response.append(TextContent(type="text", 
                        text=f"Warning: Failed to add user {user} as admin: {str(e)}"))

            if args.ttl_period:
                # Set message auto-delete timer
                await client(functions.messages.SetHistoryTTL(
                    peer=channel,
                    period=args.ttl_period
                ))

            # Generate invite link if it's private
            if args.private:
                invite_link = await client(functions.messages.ExportChatInvite(
                    peer=channel,
                    legacy_revoke_permanent=False
                ))
                response.append(TextContent(type="text", 
                    text=f"Channel '{args.title}' created successfully.\n"
                         f"ID: {channel.id}\n"
                         f"Invite Link: {invite_link.link}"))
            else:
                response.append(TextContent(type="text", 
                    text=f"Channel '{args.title}' created successfully.\n"
                         f"ID: {channel.id}"))

        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to create channel: {str(e)}"))

    return response


### InviteToChat ###


class InviteToChat(ToolArgs):
    """
    Invite users to a chat.
    
    Invites one or more users to a group or channel.
    Users can be specified by username or user ID.
    """

    chat_id: int
    users: list[str | int]  # List of usernames or user IDs to invite


@tool_runner.register
async def invite_to_chat(
    args: InviteToChat,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[InviteToChat] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            chat = await client.get_entity(args.chat_id)
            results = []
            
            for user in args.users:
                try:
                    user_entity = await client.get_entity(user)
                    await client(functions.channels.InviteToChannel(
                        channel=chat,
                        users=[user_entity]
                    ))
                    results.append(f"Successfully invited {user}")
                except Exception as e:
                    results.append(f"Failed to invite {user}: {str(e)}")
            
            response.append(TextContent(type="text", text="\n".join(results)))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to process invites: {str(e)}"))

    return response


### GetChatMembers ###


class GetChatMembers(ToolArgs):
    """
    Get a list of chat members.
    
    Retrieves members of a group or channel with their roles (admin, member, etc.).
    Can filter by role and search by name.
    """

    chat_id: int
    filter: str = "all"  # One of: all, admin, bot, banned, restricted
    search: str | None = None  # Optional search query for usernames/names
    limit: int = 100  # Maximum number of members to retrieve


@tool_runner.register
async def get_chat_members(
    args: GetChatMembers,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[GetChatMembers] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            # Map filter string to appropriate filter object
            filter_map = {
                "admin": types.ChannelParticipantsAdmins(),
                "bot": types.ChannelParticipantsBots(),
                "banned": types.ChannelParticipantsBanned(),
                "restricted": types.ChannelParticipantsRestricted(),
                "all": types.ChannelParticipantsSearch(q="")
            }
            
            filter_obj = filter_map.get(args.filter.lower(), filter_map["all"])
            if args.search and args.filter.lower() == "all":
                filter_obj = types.ChannelParticipantsSearch(q=args.search)

            members = await client(functions.channels.GetParticipants(
                channel=args.chat_id,
                filter=filter_obj,
                offset=0,
                limit=args.limit,
                hash=0
            ))

            # Format member information
            member_info = []
            for participant in members.participants:
                user = next((u for u in members.users if u.id == participant.user_id), None)
                if user:
                    role = "Owner" if isinstance(participant, types.ChannelParticipantCreator) else \
                          "Admin" if isinstance(participant, types.ChannelParticipantAdmin) else \
                          "Member"
                    username = f"@{user.username}" if user.username else "No username"
                    name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
                    member_info.append(f"{name} ({username}) - {role}")

            if member_info:
                response.append(TextContent(type="text", 
                    text=f"Chat members ({len(member_info)}):\n" + "\n".join(member_info)))
            else:
                response.append(TextContent(type="text", text="No members found matching criteria"))

        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to get chat members: {str(e)}"))

    return response


### GetChatPermissions ###


class GetChatPermissions(ToolArgs):
    """
    Get chat permissions.
    
    Retrieves the current permission settings for a group or channel.
    """

    chat_id: int


@tool_runner.register
async def get_chat_permissions(
    args: GetChatPermissions,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[GetChatPermissions] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            chat = await client.get_entity(args.chat_id)
            full_chat = await client(functions.channels.GetFullChannel(
                channel=chat
            ))

            # Get default permissions
            default_rights = full_chat.full_chat.default_banned_rights
            
            # Format permissions
            permissions = [
                f"Send Messages: {not default_rights.send_messages}",
                f"Send Media: {not default_rights.send_media}",
                f"Send Stickers & GIFs: {not default_rights.send_gifs}",
                f"Send Polls: {not default_rights.send_polls}",
                f"Embed Links: {not default_rights.embed_links}",
                f"Invite Users: {not default_rights.invite_users}",
                f"Pin Messages: {not default_rights.pin_messages}",
                f"Change Info: {not default_rights.change_info}"
            ]

            response.append(TextContent(type="text", 
                text=f"Chat Permissions for {chat.title}:\n" + "\n".join(permissions)))

        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to get chat permissions: {str(e)}"))

    return response


### UpdateChatPhoto ###


class UpdateChatPhoto(ToolArgs):
    """
    Update a chat's profile photo.
    
    Changes the profile photo of a group or channel.
    Accepts a local file path or URL to the new photo.
    """

    chat_id: int
    photo_path: str  # Local file path or URL to photo


@tool_runner.register
async def update_chat_photo(
    args: UpdateChatPhoto,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[UpdateChatPhoto] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            chat = await client.get_entity(args.chat_id)
            await client(functions.channels.EditPhotoRequest(
                channel=chat,
                photo=await client.upload_file(args.photo_path)
            ))
            
            response.append(TextContent(type="text", 
                text=f"Successfully updated chat photo"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to update chat photo: {str(e)}"))

    return response


### UpdateChatInfo ###


class UpdateChatInfo(ToolArgs):
    """
    Update a chat's basic information.
    
    Changes the title and/or description of a group or channel.
    At least one of title or about must be provided.
    """

    chat_id: int
    title: str | None = None  # New chat title
    about: str | None = None  # New chat description/about text


@tool_runner.register
async def update_chat_info(
    args: UpdateChatInfo,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[UpdateChatInfo] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            chat = await client.get_entity(args.chat_id)
            updates = []

            if args.title:
                await client(functions.channels.EditTitleRequest(
                    channel=chat,
                    title=args.title
                ))
                updates.append("title")

            if args.about:
                await client(functions.channels.EditAboutRequest(
                    channel=chat,
                    about=args.about
                ))
                updates.append("description")

            if updates:
                response.append(TextContent(type="text", 
                    text=f"Successfully updated chat {', '.join(updates)}"))
            else:
                response.append(TextContent(type="text", 
                    text="No updates provided. Specify either title or about"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to update chat info: {str(e)}"))

    return response


### SetChatPermissions ###


class SetChatPermissions(ToolArgs):
    """
    Set default permissions for all members in a chat.
    
    Updates the default permissions for non-admin members in a group or channel.
    Permissions not specified will retain their current values.
    """

    chat_id: int
    send_messages: bool | None = None
    send_media: bool | None = None
    send_stickers: bool | None = None
    send_gifs: bool | None = None
    send_games: bool | None = None
    send_inline: bool | None = None
    embed_links: bool | None = None
    send_polls: bool | None = None
    change_info: bool | None = None
    invite_users: bool | None = None
    pin_messages: bool | None = None


@tool_runner.register
async def set_chat_permissions(
    args: SetChatPermissions,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[SetChatPermissions] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            chat = await client.get_entity(args.chat_id)
            
            # Get current permissions first
            full_chat = await client(functions.channels.GetFullChannel(channel=chat))
            current_rights = full_chat.full_chat.default_banned_rights

            # Update only specified permissions
            new_rights = types.ChatBannedRights(
                until_date=None,
                send_messages=not args.send_messages if args.send_messages is not None else current_rights.send_messages,
                send_media=not args.send_media if args.send_media is not None else current_rights.send_media,
                send_stickers=not args.send_stickers if args.send_stickers is not None else current_rights.send_stickers,
                send_gifs=not args.send_gifs if args.send_gifs is not None else current_rights.send_gifs,
                send_games=not args.send_games if args.send_games is not None else current_rights.send_games,
                send_inline=not args.send_inline if args.send_inline is not None else current_rights.send_inline,
                embed_links=not args.embed_links if args.embed_links is not None else current_rights.embed_links,
                send_polls=not args.send_polls if args.send_polls is not None else current_rights.send_polls,
                change_info=not args.change_info if args.change_info is not None else current_rights.change_info,
                invite_users=not args.invite_users if args.invite_users is not None else current_rights.invite_users,
                pin_messages=not args.pin_messages if args.pin_messages is not None else current_rights.pin_messages
            )

            await client(functions.messages.EditChatDefaultBannedRights(
                peer=chat,
                banned_rights=new_rights
            ))

            response.append(TextContent(type="text", text="Successfully updated chat permissions"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to set chat permissions: {str(e)}"))

    return response


### ManageUser ###


class ManageUser(ToolArgs):
    """
    Manage a user in a chat (kick, ban, or unban).
    
    Allows kicking or banning users from a group or channel.
    Can also be used to unban previously banned users.
    """

    chat_id: int
    user_id: int | str  # User ID or username to manage
    action: str  # One of: kick, ban, unban
    ban_duration: int | None = None  # Duration in seconds for temporary bans


@tool_runner.register
async def manage_user(
    args: ManageUser,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[ManageUser] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            chat = await client.get_entity(args.chat_id)
            user = await client.get_entity(args.user_id)

            if args.action.lower() == "kick":
                await client.kick_participant(chat, user)
                response.append(TextContent(type="text", 
                    text=f"Successfully kicked user {user.id} from the chat"))

            elif args.action.lower() == "ban":
                rights = types.ChatBannedRights(
                    until_date=None if not args.ban_duration else int(time.time() + args.ban_duration),
                    view_messages=True
                )
                await client(functions.channels.EditBannedRequest(
                    channel=chat,
                    participant=user,
                    banned_rights=rights
                ))
                duration_text = " permanently" if not args.ban_duration else f" for {args.ban_duration} seconds"
                response.append(TextContent(type="text", 
                    text=f"Successfully banned user {user.id}{duration_text}"))

            elif args.action.lower() == "unban":
                rights = types.ChatBannedRights(
                    until_date=None,
                    view_messages=False
                )
                await client(functions.channels.EditBannedRequest(
                    channel=chat,
                    participant=user,
                    banned_rights=rights
                ))
                response.append(TextContent(type="text", 
                    text=f"Successfully unbanned user {user.id}"))

            else:
                response.append(TextContent(type="text", 
                    text="Invalid action. Use 'kick', 'ban', or 'unban'"))

        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to {args.action} user: {str(e)}"))

    return response


### GetBannedUsers ###


class GetBannedUsers(ToolArgs):
    """
    Get a list of banned users in a chat.
    
    Retrieves all users that are currently banned from a group or channel.
    """

    chat_id: int
    limit: int = 100  # Maximum number of banned users to retrieve


@tool_runner.register
async def get_banned_users(
    args: GetBannedUsers,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[GetBannedUsers] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            chat = await client.get_entity(args.chat_id)
            
            banned = await client(functions.channels.GetParticipants(
                channel=chat,
                filter=types.ChannelParticipantsBanned(),
                offset=0,
                limit=args.limit,
                hash=0
            ))

            if not banned.participants:
                response.append(TextContent(type="text", text="No banned users found"))
                return response

            banned_info = []
            for participant in banned.participants:
                user = next((u for u in banned.users if u.id == participant.user_id), None)
                if user:
                    username = f"@{user.username}" if user.username else "No username"
                    name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
                    banned_info.append(f"{name} ({username}) - ID: {user.id}")

            response.append(TextContent(type="text", 
                text=f"Banned users ({len(banned_info)}):\n" + "\n".join(banned_info)))

        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to get banned users: {str(e)}"))

    return response


### LeaveChat ###


class LeaveChat(ToolArgs):
    """
    Leave a chat.
    
    Allows the bot to leave a group, channel, or chat.
    """

    chat_id: int


@tool_runner.register
async def leave_chat(
    args: LeaveChat,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[LeaveChat] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            chat = await client.get_entity(args.chat_id)
            await client(functions.channels.LeaveChannel(
                channel=chat
            ))
            response.append(TextContent(type="text", text="Successfully left the chat"))
        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to leave chat: {str(e)}"))

    return response


### GetChatInviteLink ###


class GetChatInviteLink(ToolArgs):
    """
    Get or create an invite link for a chat.
    
    Generates a new invite link or retrieves the existing one.
    Can optionally create a new link even if one exists.
    """

    chat_id: int
    new_link: bool = False  # Whether to generate a new link
    expire_date: int | None = None  # Optional expiration date (Unix timestamp)
    usage_limit: int | None = None  # Optional maximum number of users


@tool_runner.register
async def get_chat_invite_link(
    args: GetChatInviteLink,
) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
    client: TelegramClient
    logger.info("method[GetChatInviteLink] args[%s]", args)

    response: list[TextContent] = []
    async with create_client() as client:
        try:
            chat = await client.get_entity(args.chat_id)
            
            if args.new_link:
                # Generate new invite link with optional parameters
                result = await client(functions.messages.ExportChatInviteRequest(
                    peer=chat,
                    expire_date=args.expire_date,
                    usage_limit=args.usage_limit
                ))
                response.append(TextContent(type="text", 
                    text=f"Generated new invite link: {result.link}"))
            else:
                # Get existing invite link
                full_chat = await client(functions.channels.GetFullChannel(
                    channel=chat
                ))
                if hasattr(full_chat.full_chat, 'exported_invite') and full_chat.full_chat.exported_invite:
                    response.append(TextContent(type="text", 
                        text=f"Current invite link: {full_chat.full_chat.exported_invite.link}"))
                else:
                    response.append(TextContent(type="text", 
                        text="No invite link exists. Set new_link=True to generate one."))

        except Exception as e:
            response.append(TextContent(type="text", text=f"Failed to get/create invite link: {str(e)}"))

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
