# ruff: noqa: T201
from __future__ import annotations

from functools import cache
from getpass import getpass

from pydantic_settings import BaseSettings
from telethon import TelegramClient  # type: ignore[import-untyped]
from telethon.errors.rpcerrorlist import SessionPasswordNeededError  # type: ignore[import-untyped]
from telethon.tl.types import User  # type: ignore[import-untyped]
from xdg_base_dirs import xdg_state_home  # type: ignore[import-error]


class TelegramSettings(BaseSettings):
    api_id: str
    api_hash: str

    class Config:
        env_prefix = "TELEGRAM_"
        env_file = ".env"


async def connect_to_telegram(api_id: str | None, api_hash: str | None, phone_number: str) -> None:
    user_session = create_client(api_id=api_id, api_hash=api_hash)
    await user_session.connect()

    result = await user_session.send_code_request(phone_number)
    code = input("Enter login code: ")
    try:
        await user_session.sign_in(
            phone=phone_number,
            code=code,
            phone_code_hash=result.phone_code_hash,
        )
    except SessionPasswordNeededError:
        password = getpass("Enter 2FA password: ")
        await user_session.sign_in(password=password)

    user = await user_session.get_me()
    if isinstance(user, User):
        print(f"Hey {user.username}! You are connected!")
    else:
        print("Connected!")
    print("You can now use the mcp-telegram server.")


async def logout_from_telegram() -> None:
    user_session = create_client()
    await user_session.connect()
    await user_session.log_out()
    print("You are now logged out from Telegram.")


@cache
def create_client(
    api_id: str | None = None,
    api_hash: str | None = None,
    session_name: str = "mcp_telegram_session",
) -> TelegramClient:
    if api_id is not None and api_hash is not None:
        config = TelegramSettings(api_id=api_id, api_hash=api_hash)
    else:
        config = TelegramSettings()
    state_home = xdg_state_home() / "mcp-telegram"
    state_home.mkdir(parents=True, exist_ok=True)
    return TelegramClient(state_home / session_name, config.api_id, config.api_hash, base_logger="telethon")
