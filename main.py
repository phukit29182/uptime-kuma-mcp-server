from pydantic import Field
from mcp.server.fastmcp import FastMCP
from uptime_kuma_api import UptimeKumaApi, MonitorType
import os
import asyncio
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

logger.info("Initializing FastMCP server instance for 'UptimeKumaMcpServer'...")
mcp = FastMCP("UptimeKumaMcpServer")
logger.info(f"FastMCP toolset name set to: '{mcp.name}'")


async def login_uptime_kuma() -> UptimeKumaApi:
    kuma_url = os.getenv("KUMA_URL")
    kuma_username = os.getenv("KUMA_USERNAME")
    kuma_password = os.getenv("KUMA_PASSWORD")
    if not all([kuma_url, kuma_username, kuma_password]):
        error_msg = "KUMA_URL, KUMA_USERNAME, or KUMA_PASSWORD environment variables are not set."
        logger.error(error_msg)
        raise ValueError(error_msg) # Fail early if config is missing
    api = UptimeKumaApi(kuma_url)
    try:
        api.login(kuma_username, kuma_password)
        logger.info("Successfully logged in to Uptime Kuma API.")
    except Exception as e:
        logger.error(f"Failed to login to Uptime Kuma: {e}")
        raise # Re-raise to let the MCP tool handler know something went wrong
    return api

@mcp.tool()
async def add_monitors(urls: list[str] = Field(description="List of monitoring URLs...")):
    try:
        api = await login_uptime_kuma()
        def add_single_monitor(url_to_add):
            try:
                name = url_to_add.split("//")[-1].split("/")[0]
                logger.info(f"Adding monitor: {name} ({url_to_add})")
                response = api.add_monitor(type=MonitorType.HTTP, name=name, url=url_to_add)
                logger.info(f"Successfully added monitor: {name} ({url_to_add}). Response: {response}")
                return {"url": url_to_add, "status": "success", "response": response}
            except Exception as e:
                logger.error(f"Error adding monitor {url_to_add}: {str(e)}")
                return {"url": url_to_add, "status": "error", "error_message": str(e)}

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        tasks = [loop.run_in_executor(None, add_single_monitor, url) for url in urls]
        results = await asyncio.gather(*tasks)
        success_count = sum(1 for r in results if r["status"] == "success")
        logger.info(f"Batch addition completed. Success count: {success_count}/{len(urls)}")
        return {
            "monitor_addition_results": results,
            "kuma_url": os.getenv("KUMA_URL"),
            "total_requested": len(urls),
            "successfully_added": success_count,
        }
    except Exception as e:
        logger.error(f"Error occurred during batch monitor addition: {str(e)}")
        raise

@mcp.tool()
async def get_monitors():
    try:
        api = await login_uptime_kuma()
        monitors_data = api.get_monitors()
        trimmed_monitors = [
            {"id": m["id"], "name": m["name"], "url": m.get("url"), "type": m.get("type", "unknown"), "active": m["active"]}
            for m in monitors_data
        ]
        logger.info(f"Successfully retrieved {len(trimmed_monitors)} monitors.")
        return {"monitors": trimmed_monitors, "total_count": len(trimmed_monitors), "kuma_url": os.getenv("KUMA_URL")}
    except Exception as e:
        logger.error(f"Error occurred while getting monitor list: {str(e)}")
        raise

@mcp.tool()
async def delete_monitors(ids: list[int] = Field(description="List of monitor IDs to delete")):
    try:
        api = await login_uptime_kuma()
        def delete_single_monitor(monitor_id):
            try:
                logger.info(f"Attempting to delete monitor ID: {monitor_id}")
                response = api.delete_monitor(monitor_id)
                logger.info(f"Response for deleting monitor ID {monitor_id}: {response}")
                if response.get("ok") and response.get("msg") == "Deleted Successfully.":
                    return {"id": monitor_id, "status": "success", "response": response}
                else:
                    error_msg = response.get("msg", "Unknown error from API")
                    logger.warning(f"Monitor ID {monitor_id} possibly not deleted. API response: {response}")
                    return {"id": monitor_id, "status": "failed", "error_message": error_msg, "response": response}
            except Exception as e:
                logger.error(f"Error deleting monitor ID {monitor_id}: {str(e)}")
                return {"id": monitor_id, "status": "error", "error_message": str(e)}

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        tasks = [loop.run_in_executor(None, delete_single_monitor, id_val) for id_val in ids]
        results = await asyncio.gather(*tasks)
        success_count = sum(1 for r in results if r["status"] == "success")
        logger.info(f"Batch deletion completed. Success count: {success_count}/{len(ids)}")
        return {
            "monitor_deletion_results": results,
            "total_requested": len(ids),
            "successfully_deleted": success_count,
            "kuma_url": os.getenv("KUMA_URL"),
        }
    except Exception as e:
        logger.error(f"Error occurred during batch monitor deletion: {str(e)}")
        raise

@mcp.tool()
async def pause_monitor(monitor_id: int = Field(description="The ID of the monitor to pause.")):
    """
    Pauses a specific monitor in Uptime Kuma.
    """
    try:
        api = await login_uptime_kuma()

        def _pause_monitor_sync(mid):
            try:
                logger.info(f"Attempting to pause monitor ID: {mid}")
                response = api.pause_monitor(monitor_id=mid) # Corrected to use mid
                logger.info(f"Response for pausing monitor ID {mid}: {response}")
                if response.get("ok"):
                    return {"id": mid, "status": "success", "message": response.get("msg", "Paused successfully."), "response": response}
                else:
                    error_msg = response.get("msg", "Unknown error from API during pause")
                    logger.warning(f"Monitor ID {mid} possibly not paused. API response: {response}")
                    return {"id": mid, "status": "failed", "error_message": error_msg, "response": response}
            except Exception as e_sync:
                logger.error(f"Error pausing monitor ID {mid} (sync part): {str(e_sync)}")
                return {"id": mid, "status": "error", "error_message": str(e_sync)}

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        result = await loop.run_in_executor(None, _pause_monitor_sync, monitor_id)
        return result

    except Exception as e:
        logger.error(f"Error occurred while pausing monitor ID {monitor_id}: {str(e)}")
        raise # Re-raise for MCP framework to handle

@mcp.tool()
async def resume_monitor(monitor_id: int = Field(description="The ID of the monitor to resume.")):
    """
    Resumes a specific monitor in Uptime Kuma.
    """
    try:
        api = await login_uptime_kuma()

        def _resume_monitor_sync(mid):
            try:
                logger.info(f"Attempting to resume monitor ID: {mid}")
                response = api.resume_monitor(monitor_id=mid) # Corrected to use mid
                logger.info(f"Response for resuming monitor ID {mid}: {response}")
                if response.get("ok"):
                    return {"id": mid, "status": "success", "message": response.get("msg", "Resumed successfully."), "response": response}
                else:
                    error_msg = response.get("msg", "Unknown error from API during resume")
                    logger.warning(f"Monitor ID {mid} possibly not resumed. API response: {response}")
                    return {"id": mid, "status": "failed", "error_message": error_msg, "response": response}
            except Exception as e_sync:
                logger.error(f"Error resuming monitor ID {mid} (sync part): {str(e_sync)}")
                return {"id": mid, "status": "error", "error_message": str(e_sync)}
        loop = asyncio.get_running_loop() if hasattr(asyncio, 'get_running_loop') else asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _resume_monitor_sync, monitor_id)
        return result
    except Exception as e:
        logger.error(f"Error occurred while resuming monitor ID {monitor_id}: {str(e)}")
        raise # Re-raise for MCP framework to handle

@mcp.tool()
async def get_monitor_beats(monitor_id: int = Field(description="The ID of the monitor."),
                            hours: int = Field(default=1, description="Period time in hours from now to retrieve beats for.")):
    """
    Retrieves heartbeats for a specific monitor within a given time range (in hours from now).
    """
    try:
        api = await login_uptime_kuma()

        def _get_monitor_beats_sync(mid, num_hours):
            try:
                logger.info(f"Attempting to retrieve beats for monitor ID: {mid} for the last {num_hours} hours.")
                # The uptime-kuma-api expects monitor_id and hours as positional arguments
                beats = api.get_monitor_beats(mid, num_hours)
                logger.info(f"Successfully retrieved {len(beats)} beats for monitor ID {mid}.")
                return {"id": mid, "status": "success", "beats": beats, "count": len(beats)}
            except Exception as e_sync:
                logger.error(f"Error retrieving beats for monitor ID {mid} (sync part): {str(e_sync)}")
                return {"id": mid, "status": "error", "error_message": str(e_sync)}

        loop = asyncio.get_running_loop() if hasattr(asyncio, 'get_running_loop') else asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _get_monitor_beats_sync, monitor_id, hours)
        return result

    except Exception as e:
        logger.error(f"Error occurred while getting monitor beats for ID {monitor_id}: {str(e)}")
        raise

@mcp.tool()
async def edit_monitor(monitor_id: int = Field(description="The ID of the monitor to edit."),
                       options: dict = Field(description="Dictionary of monitor attributes to update. Refer to Uptime Kuma API for available fields (e.g., name, url, interval, etc.).")):
    """
    Edits an existing monitor in Uptime Kuma.
    """
    try:
        api = await login_uptime_kuma()

        def _edit_monitor_sync(mid, opts):
            try:
                logger.info(f"Attempting to edit monitor ID: {mid} with options: {opts}")
                response = api.edit_monitor(monitor_id=mid, **opts)
                logger.info(f"Response for editing monitor ID {mid}: {response}")
                if response.get("ok"):
                    return {"id": mid, "status": "success", "message": response.get("msg", "Monitor edited successfully."), "response": response}
                else:
                    error_msg = response.get("msg", "Unknown error from API during edit")
                    logger.warning(f"Monitor ID {mid} possibly not edited. API response: {response}")
                    return {"id": mid, "status": "failed", "error_message": error_msg, "response": response}
            except Exception as e_sync:
                logger.error(f"Error editing monitor ID {mid} (sync part): {str(e_sync)}")
                return {"id": mid, "status": "error", "error_message": str(e_sync)}

        loop = asyncio.get_running_loop() if hasattr(asyncio, 'get_running_loop') else asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _edit_monitor_sync, monitor_id, options)
        return result

    except Exception as e:
        logger.error(f"Error occurred while editing monitor ID {monitor_id}: {str(e)}")
        raise

@mcp.tool()
async def add_monitor_tag(monitor_id: int = Field(description="The ID of the monitor."),
                          tag_id: int = Field(description="The ID of the tag to add."),
                          value: str = Field(description="The value for the tag.")):
    """
    Adds a tag to a specific monitor.
    """
    try:
        api = await login_uptime_kuma()

        def _add_monitor_tag_sync(mid, tid, val):
            try:
                logger.info(f"Attempting to add tag ID: {tid} with value '{val}' to monitor ID: {mid}")
                response = api.add_monitor_tag(monitor_id=mid, tag_id=tid, value=val)
                logger.info(f"Response for adding tag to monitor ID {mid}: {response}")
                if response.get("ok"):
                    return {"monitor_id": mid, "tag_id": tid, "status": "success", "message": response.get("msg", "Tag added successfully."), "response": response}
                else:
                    error_msg = response.get("msg", "Unknown error from API during tag addition")
                    logger.warning(f"Tag ID {tid} possibly not added to monitor ID {mid}. API response: {response}")
                    return {"monitor_id": mid, "tag_id": tid, "status": "failed", "error_message": error_msg, "response": response}
            except Exception as e_sync:
                logger.error(f"Error adding tag ID {tid} to monitor ID {mid} (sync part): {str(e_sync)}")
                return {"monitor_id": mid, "tag_id": tid, "status": "error", "error_message": str(e_sync)}

        loop = asyncio.get_running_loop() if hasattr(asyncio, 'get_running_loop') else asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _add_monitor_tag_sync, monitor_id, tag_id, value)
        return result

    except Exception as e:
        logger.error(f"Error occurred while adding tag to monitor ID {monitor_id}: {str(e)}")
        raise

@mcp.tool()
async def delete_monitor_tag(monitor_id: int = Field(description="The ID of the monitor."),
                             tag_id: int = Field(description="The ID of the tag to delete.")):
    """
    Deletes a tag from a specific monitor.
    """
    try:
        api = await login_uptime_kuma()

        def _delete_monitor_tag_sync(mid, tid):
            try:
                logger.info(f"Attempting to delete tag ID: {tid} from monitor ID: {mid}")
                response = api.delete_monitor_tag(monitor_id=mid, tag_id=tid)
                logger.info(f"Response for deleting tag from monitor ID {mid}: {response}")
                if response.get("ok"):
                    return {"monitor_id": mid, "tag_id": tid, "status": "success", "message": response.get("msg", "Tag deleted successfully."), "response": response}
                else:
                    error_msg = response.get("msg", "Unknown error from API during tag deletion")
                    logger.warning(f"Tag ID {tid} possibly not deleted from monitor ID {mid}. API response: {response}")
                    return {"monitor_id": mid, "tag_id": tid, "status": "failed", "error_message": error_msg, "response": response}
            except Exception as e_sync:
                logger.error(f"Error deleting tag ID {tid} from monitor ID {mid} (sync part): {str(e_sync)}")
                return {"monitor_id": mid, "tag_id": tid, "status": "error", "error_message": str(e_sync)}

        loop = asyncio.get_running_loop() if hasattr(asyncio, 'get_running_loop') else asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _delete_monitor_tag_sync, monitor_id, tag_id)
        return result

    except Exception as e:
        logger.error(f"Error occurred while deleting tag from monitor ID {monitor_id}: {str(e)}")
        raise

@mcp.tool()
async def get_status_page(slug: str = Field(description="The slug of the status page.")):
    """
    Retrieves details for a specific status page by its slug.
    """
    try:
        api = await login_uptime_kuma()

        def _get_status_page_sync(s):
            try:
                logger.info(f"Attempting to retrieve status page with slug: {s}")
                status_page_data = api.get_status_page(slug=s)
                logger.info(f"Successfully retrieved status page with slug: {s}")
                return {"slug": s, "status": "success", "data": status_page_data}
            except Exception as e_sync:
                logger.error(f"Error retrieving status page with slug {s} (sync part): {str(e_sync)}")
                return {"slug": s, "status": "error", "error_message": str(e_sync)}

        loop = asyncio.get_running_loop() if hasattr(asyncio, 'get_running_loop') else asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _get_status_page_sync, slug)
        return result

    except Exception as e:
        logger.error(f"Error occurred while getting status page with slug {slug}: {str(e)}")
        raise

@mcp.tool()
async def get_heartbeats(offset: int = Field(default=0, description="Offset for pagination."),
                         limit: int = Field(default=100, description="Limit for number of heartbeats to return per page.")):
    """
    Retrieves heartbeat monitor data with pagination.
    Note: This tool fetches all heartbeats from Uptime Kuma first, then applies pagination.
    """
    try:
        api = await login_uptime_kuma()

        def _get_heartbeats_sync(p_offset, p_limit):
            try:
                logger.info("Attempting to retrieve all heartbeats.")
                heartbeats_data = api.get_heartbeats()
                total_heartbeats = len(heartbeats_data)
                logger.info(f"Successfully retrieved {total_heartbeats} heartbeats from Uptime Kuma API.")

                # Apply pagination
                start_index = p_offset
                end_index = p_offset + p_limit
                paginated_heartbeats = heartbeats_data[start_index:end_index]
                
                logger.info(f"Returning {len(paginated_heartbeats)} heartbeats after pagination (offset: {p_offset}, limit: {p_limit}).")
                return {"status": "success",
                        "data": paginated_heartbeats,
                        "total_available": total_heartbeats,
                        "count_returned": len(paginated_heartbeats),
                        "offset": p_offset,
                        "limit": p_limit}
            except Exception as e_sync:
                logger.error(f"Error retrieving heartbeats (sync part): {str(e_sync)}")
                return {"status": "error", "error_message": str(e_sync)}

        loop = asyncio.get_running_loop() if hasattr(asyncio, 'get_running_loop') else asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _get_heartbeats_sync, offset, limit)
        return result

    except Exception as e:
        logger.error(f"Error occurred while getting all heartbeats: {str(e)}")
        raise

@mcp.tool()
async def get_tags():
    """
    Retrieves all tags defined in Uptime Kuma.
    """
    try:
        api = await login_uptime_kuma()

        def _get_tags_sync():
            try:
                logger.info("Attempting to retrieve all tags.")
                tags_data = api.get_tags()
                logger.info(f"Successfully retrieved {len(tags_data)} tags.")
                return {"status": "success", "data": tags_data, "count": len(tags_data)}
            except Exception as e_sync:
                logger.error(f"Error retrieving tags (sync part): {str(e_sync)}")
                return {"status": "error", "error_message": str(e_sync)}

        loop = asyncio.get_running_loop() if hasattr(asyncio, 'get_running_loop') else asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _get_tags_sync)
        return result

    except Exception as e:
        logger.error(f"Error occurred while getting all tags: {str(e)}")
        raise

def main_stdio():
    logger.info("Starting MCP server with stdio transport...")
    mcp.run(transport="stdio")

def main_sse():
    intended_host = os.getenv("MCP_HOST", "0.0.0.0")
    intended_port = int(os.getenv("MCP_PORT", "8000"))
    logger.info(f"Attempting to start MCP server via main_sse(). Intended host from env: '{intended_host}', Intended port from env: {intended_port}")
    mcp.run(transport="sse")

if __name__ == "__main__":
    logger.info("Starting MCP server in STDIO mode as per __main__ block...")
    main_stdio()
    logger.info("MCP server (stdio mode) has finished or exited.")