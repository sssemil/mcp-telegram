import asyncio
from functools import cache
from getpass import getpass

from pydantic_settings import BaseSettings
from telethon import TelegramClient  # type: ignore[import-untyped]
from telethon.errors.rpcerrorlist import SessionPasswordNeededError  # type: ignore[import-untyped]


class TelegramSettings(BaseSettings):
    api_id: int
    api_hash: str
    phone_number: str

    class Config:
        env_prefix = "TELEGRAM_"
        env_file = ".env"


async def _connect_to_telegram() -> None:
    settings = TelegramSettings()
    user_session = create_client()
    await user_session.connect()

    result = await user_session.send_code_request(settings.phone_number)
    code = input("Enter login code: ")
    try:
        await user_session.sign_in(
            phone=settings.phone_number,
            code=code,
            phone_code_hash=result.phone_code_hash,
        )
    except SessionPasswordNeededError:
        password = getpass("Enter 2FA password: ")
        await user_session.sign_in(password=password)


def connect() -> None:
    asyncio.run(_connect_to_telegram())


@cache
def create_client(session_name: str = "mcp_telegram_session") -> TelegramClient:
    config = TelegramSettings()
    return TelegramClient(session_name, config.api_id, config.api_hash, base_logger="telethon")
