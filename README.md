# Uptime Kuma MCP Server

This project provides a FastMCP (Message Control Protocol) server that acts as an intermediary to interact with an Uptime Kuma instance. It exposes a set of tools to manage monitors, tags, status pages, and retrieve heartbeat data from Uptime Kuma.

## Features

The server exposes the following tools:

*   **Login to Uptime Kuma:** (Internal function, used by all tools)
*   **`add_monitors`**: Adds multiple HTTP monitors to Uptime Kuma.
*   **`get_monitors`**: Retrieves a list of all monitors.
*   **`delete_monitors`**: Deletes specified monitors by their IDs.
*   **`pause_monitor`**: Pauses a specific monitor.
*   **`resume_monitor`**: Resumes a specific monitor.
*   **`get_monitor_beats`**: Retrieves heartbeats for a specific monitor.
*   **`edit_monitor`**: Edits an existing monitor's attributes.
*   **`add_monitor_tag`**: Adds a tag to a specific monitor.
*   **`delete_monitor_tag`**: Deletes a tag from a specific monitor.
*   **`get_status_page`**: Retrieves details for a specific status page.
*   **`get_heartbeats`**: Retrieves heartbeats for a specific monitor within a time range, with pagination.
*   **`get_tags`**: Retrieves all tags defined in Uptime Kuma.

## How it Works

1.  **FastMCP Server:** The core of the application is a `FastMCP` server instance. This server listens for incoming requests to execute predefined "tools".
2.  **Uptime Kuma API Integration:** Each tool, when invoked, first attempts to log in to the configured Uptime Kuma instance using the `uptime-kuma-api` Python client library.
3.  **Asynchronous Operations:** The server is built using `asyncio` for non-blocking I/O. Since the `uptime-kuma-api` library is synchronous, its calls are wrapped in `loop.run_in_executor` to prevent blocking the server's event loop.
4.  **Environment Configuration:** Critical configuration details such as Uptime Kuma credentials and server binding information are managed via environment variables, loaded from a `.env` file.
5.  **Tool Definitions:** Each exposed functionality (e.g., `add_monitors`, `get_monitors`) is defined as an asynchronous function decorated with `@mcp.tool()`. These tools handle the logic for interacting with the Uptime Kuma API and formatting the response.

## Prerequisites

*   Python 3.7+ (due to `asyncio.get_running_loop()`)
*   An Uptime Kuma instance.
*   Access credentials (username, password) for the Uptime Kuma instance.

## Setup

1.  **Clone the repository (if applicable):**
    ```bash
    git clone <repository_url>
    cd uptime-kuma-mcp-server
    ```

2.  **Install dependencies:**
    It's recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

## Running the Server

The server can be run in two modes:

1.  **STDIO Mode (Default):**
    This mode uses standard input/output for communication. It's typically used when the server is managed as a subprocess by another application.
    ```bash
    python main.py
    ```
    The server will start and log its activity to the console.

2.  **SSE (Server-Sent Events) Mode:**
    This mode runs an HTTP server that communicates using Server-Sent Events. To run in this mode, you would need to modify the `if __name__ == "__main__":` block in `main.py` to call `main_sse()` instead of `main_stdio()`.

    Example modification in `main.py`:
    ```python
    if __name__ == "__main__":
        # logger.info("Starting MCP server in STDIO mode as per __main__ block...")
        # main_stdio()
        # logger.info("MCP server (stdio mode) has finished or exited.")

        logger.info("Starting MCP server in SSE mode...")
        main_sse() # Call main_sse() here
        logger.info("MCP server (SSE mode) has finished or exited.")
    ```
    Then run:
    ```bash
    python main.py
    ```
    The server will listen on the host and port specified by `MCP_HOST` and `MCP_PORT` environment variables (defaults to `0.0.0.0:8000`).

## Tool Details

All tools first attempt to log in to Uptime Kuma. If login fails, the tool execution will fail.

### `add_monitors(urls: list[str])`
*   **Description:** Adds multiple HTTP monitors to Uptime Kuma.
*   **Parameters:**
    *   `urls` (list of strings): A list of URLs to create monitors for. The monitor name is derived from the URL.
*   **Returns:** A dictionary containing `monitor_addition_results`, `kuma_url`, `total_requested`, and `successfully_added`.

### `get_monitors()`
*   **Description:** Retrieves a list of all monitors from Uptime Kuma.
*   **Parameters:** None.
*   **Returns:** A dictionary containing `monitors` (trimmed list), `total_count`, and `kuma_url`.

### `delete_monitors(ids: list[int])`
*   **Description:** Deletes specified monitors by their IDs.
*   **Parameters:**
    *   `ids` (list of integers): A list of monitor IDs to delete.
*   **Returns:** A dictionary containing `monitor_deletion_results`, `total_requested`, `successfully_deleted`, and `kuma_url`.

### `pause_monitor(monitor_id: int)`
*   **Description:** Pauses a specific monitor.
*   **Parameters:**
    *   `monitor_id` (integer): The ID of the monitor to pause.
*   **Returns:** A dictionary indicating success or failure, along with API response.

### `resume_monitor(monitor_id: int)`
*   **Description:** Resumes a specific monitor.
*   **Parameters:**
    *   `monitor_id` (integer): The ID of the monitor to resume.
*   **Returns:** A dictionary indicating success or failure, along with API response.

### `get_monitor_beats(monitor_id: int, hours: int = 1)`
*   **Description:** Retrieves heartbeats for a specific monitor within a given time range.
*   **Parameters:**
    *   `monitor_id` (integer): The ID of the monitor.
    *   `hours` (integer, default: 1): Period in hours from now to retrieve beats for.
*   **Returns:** A dictionary containing the `beats`, `count`, and `status`.

### `edit_monitor(monitor_id: int, options: dict)`
*   **Description:** Edits an existing monitor.
*   **Parameters:**
    *   `monitor_id` (integer): The ID of the monitor to edit.
    *   `options` (dictionary): Monitor attributes to update (e.g., `{"name": "New Name", "interval": 60}`). Refer to Uptime Kuma API for available fields.
*   **Returns:** A dictionary indicating success or failure, along with API response.

### `add_monitor_tag(monitor_id: int, tag_id: int, value: str)`
*   **Description:** Adds a tag to a specific monitor.
*   **Parameters:**
    *   `monitor_id` (integer): The ID of the monitor.
    *   `tag_id` (integer): The ID of the tag to add.
    *   `value` (string): The value for the tag.
*   **Returns:** A dictionary indicating success or failure, along with API response.

### `delete_monitor_tag(monitor_id: int, tag_id: int)`
*   **Description:** Deletes a tag from a specific monitor.
*   **Parameters:**
    *   `monitor_id` (integer): The ID of the monitor.
    *   `tag_id` (integer): The ID of the tag to delete.
*   **Returns:** A dictionary indicating success or failure, along with API response.

### `get_status_page(slug: str)`
*   **Description:** Retrieves details for a specific status page by its slug.
*   **Parameters:**
    *   `slug` (string): The slug of the status page.
*   **Returns:** A dictionary containing the status page `data` or an error message.

### `get_heartbeats(offset: int = 0, limit: int = 100)`
*   **Description:** Retrieves heartbeat monitor data with pagination.
    *   *Note: This tool fetches all heartbeats from Uptime Kuma first, then applies pagination on the server side. This might be inefficient for very large datasets.*
*   **Parameters:**
    *   `offset` (integer, default: 0): Offset for pagination.
    *   `limit` (integer, default: 100): Limit for number of heartbeats per page.
*   **Returns:** A dictionary containing paginated `data`, `total_available`, `count_returned`, `offset`, and `limit`.

### `get_tags()`
*   **Description:** Retrieves all tags defined in Uptime Kuma.
*   **Parameters:** None.
*   **Returns:** A dictionary containing the list of tags (`data`) and their `count`.

## Logging

The server uses Python's `logging` module. By default, logs are output to the console (standard output) with INFO level and include a timestamp, logger name, log level, and message.

## Error Handling

*   **Configuration Errors:** The server will fail to start (raising a `ValueError`) if essential Uptime Kuma environment variables (`KUMA_URL`, `KUMA_USERNAME`, `KUMA_PASSWORD`) are not set.
*   **API Errors:** Errors during interaction with the Uptime Kuma API (e.g., login failure, invalid monitor ID) are logged. The tools typically return a dictionary with a "status" field indicating "error" or "failed" and an "error_message".
*   **General Exceptions:** Uncaught exceptions within tool handlers are logged and re-raised, allowing the FastMCP framework to handle them appropriately (which might involve sending an error response to the client).

```