# Telegram MCP server

- [Telegram MCP server](#telegram-mcp-server)
  - [About](#about)
  - [What is MCP?](#what-is-mcp)
  - [What does this server do?](#what-does-this-server-do)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
    - [Claude Desktop Configuration](#claude-desktop-configuration)
    - [Telegram Configuration](#telegram-configuration)
  - [Development](#development)

## About

The server is a bridge between the Telegram API and the AI assistant. The server is a Python application that uses the [MCP](https://modelcontextprotocol.io).

## What is MCP?

The Model Context Protocol (MCP) is a system that lets AI apps, like Claude Desktop, connect to external tools and data sources. It gives a clear and safe way for AI assistants to work with local services and APIs while keeping the user in control.

## What does this server do?

As of not, the server provides read-only access to the Telegram API.

*The list of actions will be provded soon.*

## Prerequisites

- [`uv` tool](https://docs.astral.sh/uv/getting-started/installation/)

## Installation

1. Clone the repository
2. Install the dependencies

   ```bash
   uv sync
   ```

3. Set environment variables

   Get the API ID and hash from [Telegram API](https://my.telegram.org/auth)

   > __Note:__
   > See [Telegram Configuration](#telegram-configuration) for more details

   Create a new file called `.env` in the root of the repository with the following lines:

     ```bash
     TELEGRAM_API_ID=<your-api-id-here>
     TELEGRAM_API_HASH=<your-api-hash-here>
     TELEGRAM_PHONE_NUMBER=<your-phone-number-here>
     ```

4. Connect to the Telegram API

   ```bash
   uv run mcp-telegram-connect
   ```

   Enter the code you received from Telegram to connect to the API.

   The password may be required if you have two-factor authentication enabled.

5. Done!

   The server is now connected to the Telegram API.

## Configuration

### Claude Desktop Configuration

Configure Claude Desktop to recognize the Exa MCP server.

1. Open the Claude Desktop configuration file:
   - in MacOS, the configuration file is located at `~/Library/Application Support/Claude/claude_desktop_config.json`
   - in Windows, the configuration file is located at `%APPDATA%\Claude\claude_desktop_config.json`

   > __Note:__
   > You can also find claude_desktop_config.json inside the settings of Claude Desktop app

2. Add the server configuration

    ```json
    {
      "mcpServers": {
        "mcp-telegram": {
            "command": "$HOME/.cargo/bin/uv",
            "args": [
              "--directory",
              "<path-to-cloned-repo>",
              "run",
              "mcp-telegram-server"
            ]
          }
        }
      }
    }
    ```

    Replace `<path-to-cloned-repo>` with the path to the cloned repository.

    Ensure that the `command` points to the `uv` binary.

### Telegram Configuration

Before working with Telegram’s API, you need to get your own API ID and hash:

1. Login to your Telegram account with the phone number of the developer account to use.
1. Click under API Development tools.
1. A 'Create new application' window will appear. Fill in your application details. There is no need to enter any URL, and only the first two fields (App title and Short name) can currently be changed later.
1. Click on 'Create application' at the end. Remember that your API hash is secret and Telegram won’t let you revoke it. __Don’t post it anywhere!__

## Development

Tools can be added to the `src/mcp_telegram/tools.py` file.

How to add a new tool:

1. Create a new class that inherits from ToolArgs

   ```python
   class NewTool(ToolArgs):
       """Description of the new tool."""
       pass
   ```

   Attributes of the class will be used as arguments for the tool.
   The class docstring will be used as the tool description.

1. Implement the tool_runner function for the new class

   ```python
   @tool_runner.register
   async def new_tool(args: NewTool) -> t.Sequence[TextContent | ImageContent | EmbeddedResource]:
       pass
   ```

   The function should return a sequence of TextContent, ImageContent or EmbeddedResource.
   The function should be async and accept a single argument of the new class.

1. Done! Restart the client and the new tool should be available.

Validation can accomplished either through Claude Desktop or by running the tool directly.

To run the tool directly, use the following command:

```bash

# List all available tools
uv run cli.py list-tools

# Run the concrete tool
uv run cli.py call-tool --name ListDialogs --arguments '{"unread": true}'
```
