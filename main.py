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
        raise ValueError(error_msg)
    api = UptimeKumaApi(kuma_url)
    try:
        api.login(kuma_username, kuma_password)
        logger.info("Successfully logged in to Uptime Kuma API.")
    except Exception as e:
        logger.error(f"Failed to login to Uptime Kuma: {e}")
        raise
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
                response = api.pause_monitor(monitor_id=mid)
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
        raise

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
                response = api.resume_monitor(monitor_id=mid)
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
        raise

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
async def get_heartbeats(
    monitor_id: int = Field(description="The ID of the monitor to retrieve heartbeats for."),
    hours: int = Field(default=24, description="Period time in hours from now to retrieve beats for (e.g., 1 for last hour, 24 for last day)."),
    offset: int = Field(default=0, description="Offset for paginating the returned heartbeats list."),
    limit: int = Field(default=100, description="Limit for number of heartbeats to return per page from the fetched list.")
):
    """
    Retrieves heartbeats for a specific monitor within a given time range (in hours from now),
    then applies pagination to the results.
    """
    try:
        api = await login_uptime_kuma()

        def _get_heartbeats_for_monitor_sync(mid, num_hours, p_offset, p_limit):
            try:
                logger.info(f"Attempting to retrieve heartbeats for monitor ID: {mid} for the last {num_hours} hours.")
                heartbeats_for_monitor = api.get_heartbeats(monitor_id=mid, hours=num_hours)
                total_fetched_for_monitor = len(heartbeats_for_monitor)
                logger.info(f"Successfully retrieved {total_fetched_for_monitor} heartbeats for monitor ID {mid} for the specified {num_hours} hours.")

                start_index = p_offset
                end_index = p_offset + p_limit
                paginated_heartbeats = heartbeats_for_monitor[start_index:end_index]

                logger.info(f"Returning {len(paginated_heartbeats)} heartbeats after pagination (offset: {p_offset}, limit: {p_limit}) for monitor ID {mid}.")
                return {
                    "status": "success",
                    "monitor_id": mid,
                    "hours_queried": num_hours,
                    "data": paginated_heartbeats,
                    "total_fetched_for_this_monitor_and_period": total_fetched_for_monitor,
                    "count_returned": len(paginated_heartbeats),
                    "offset": p_offset,
                    "limit": p_limit
                }
            except Exception as e_sync:
                logger.error(f"Error retrieving heartbeats for monitor ID {mid} (sync part): {str(e_sync)}")
                return {"status": "error", "monitor_id": mid, "error_message": str(e_sync)}

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        result = await loop.run_in_executor(None, _get_heartbeats_for_monitor_sync, monitor_id, hours, offset, limit)
        return result

    except Exception as e:
        logger.error(f"Error occurred while getting monitor beats for ID {monitor_id}: {str(e)}")
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

@mcp.tool()
async def create_tag(name: str = Field(description="The name of the new tag.")):
    """
    Creates a new tag in Uptime Kuma.
    """
    try:
        api = await login_uptime_kuma()

        def _create_tag_sync(tag_name):
            try:
                logger.info(f"Attempting to create tag: {tag_name}")
                response = api.add_tag(name=tag_name)
                logger.info(f"Response for creating tag '{tag_name}': {response}")
                if response.get("ok"):
                    return {"name": tag_name, "status": "success", "message": response.get("msg", "Tag created successfully."), "response": response}
                else:
                    error_msg = response.get("msg", "Unknown error from API during tag creation")
                    logger.warning(f"Tag '{tag_name}' possibly not created. API response: {response}")
                    return {"name": tag_name, "status": "failed", "error_message": error_msg, "response": response}
            except Exception as e_sync:
                logger.error(f"Error creating tag '{tag_name}' (sync part): {str(e_sync)}")
                return {"name": tag_name, "status": "error", "error_message": str(e_sync)}

        loop = asyncio.get_running_loop() if hasattr(asyncio, 'get_running_loop') else asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _create_tag_sync, name)
        return result

    except Exception as e:
        logger.error(f"Error occurred while creating tag '{name}': {str(e)}")
        raise

@mcp.tool()
async def edit_tag(tag_id: int = Field(description="The ID of the tag to edit."),
                   new_name: str = Field(description="The new name for the tag.")):
    """
    Edits the name of an existing tag in Uptime Kuma.
    """
    try:
        api = await login_uptime_kuma()

        def _edit_tag_sync(tid, new_tag_name):
            try:
                logger.info(f"Attempting to edit tag ID: {tid} to new name: {new_tag_name}")
                response = api.edit_tag(tag_id=tid, name=new_tag_name)
                logger.info(f"Response for editing tag ID {tid}: {response}")
                if response.get("ok"):
                    return {"id": tid, "new_name": new_tag_name, "status": "success", "message": response.get("msg", "Tag edited successfully."), "response": response}
                else:
                    error_msg = response.get("msg", "Unknown error from API during tag edit")
                    logger.warning(f"Tag ID {tid} possibly not edited. API response: {response}")
                    return {"id": tid, "new_name": new_tag_name, "status": "failed", "error_message": error_msg, "response": response}
            except Exception as e_sync:
                logger.error(f"Error editing tag ID {tid} (sync part): {str(e_sync)}")
                return {"id": tid, "new_name": new_tag_name, "status": "error", "error_message": str(e_sync)}

        loop = asyncio.get_running_loop() if hasattr(asyncio, 'get_running_loop') else asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _edit_tag_sync, tag_id, new_name)
        return result

    except Exception as e:
        logger.error(f"Error occurred while editing tag ID {tag_id}: {str(e)}")
        raise

@mcp.tool()
async def delete_tag(tag_id: int = Field(description="The ID of the tag to delete.")):
    """
    Deletes a tag from Uptime Kuma.
    """
    try:
        api = await login_uptime_kuma()

        def _delete_tag_sync(tid):
            try:
                logger.info(f"Attempting to delete tag ID: {tid}")
                response = api.delete_tag(tag_id=tid)
                logger.info(f"Response for deleting tag ID {tid}: {response}")
                if response.get("ok"):
                    return {"id": tid, "status": "success", "message": response.get("msg", "Tag deleted successfully."), "response": response}
                else:
                    error_msg = response.get("msg", "Unknown error from API during tag deletion")
                    logger.warning(f"Tag ID {tid} possibly not deleted. API response: {response}")
                    return {"id": tid, "status": "failed", "error_message": error_msg, "response": response}
            except Exception as e_sync:
                logger.error(f"Error deleting tag ID {tid} (sync part): {str(e_sync)}")
                return {"id": tid, "status": "error", "error_message": str(e_sync)}

        loop = asyncio.get_running_loop() if hasattr(asyncio, 'get_running_loop') else asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _delete_tag_sync, tag_id)
        return result

    except Exception as e:
        logger.error(f"Error occurred while deleting tag ID {tag_id}: {str(e)}")
        raise

@mcp.tool()
async def create_status_page(name: str = Field(description="The name of the new status page."),
                             slug: str = Field(description="The unique slug for the status page (used in URL)."),
                             title: str = Field(None, description="The title displayed on the status page."),
                             description: str = Field(None, description="A description for the status page."),
                             ):
    """
    Creates a new status page in Uptime Kuma.
    """
    try:
        api = await login_uptime_kuma()

        def _create_status_page_sync(sp_name, sp_slug, sp_title, sp_description):
            try:
                logger.info(f"Attempting to create status page: '{sp_name}' with slug '{sp_slug}'")
                options = {
                    "title": sp_title,
                    "description": sp_description,
                }
                options = {k: v for k, v in options.items() if v is not None}

                response = api.add_status_page(name=sp_name, slug=sp_slug, **options)
                logger.info(f"Response for creating status page '{sp_name}': {response}")
                if response.get("ok"):
                    return {"name": sp_name, "slug": sp_slug, "status": "success", "message": response.get("msg", "Status page created successfully."), "response": response}
                else:
                    error_msg = response.get("msg", "Unknown error from API during status page creation")
                    logger.warning(f"Status page '{sp_name}' possibly not created. API response: {response}")
                    return {"name": sp_name, "slug": sp_slug, "status": "failed", "error_message": error_msg, "response": response}
            except Exception as e_sync:
                logger.error(f"Error creating status page '{sp_name}' (sync part): {str(e_sync)}")
                return {"name": sp_name, "slug": sp_slug, "status": "error", "error_message": str(e_sync)}

        loop = asyncio.get_running_loop() if hasattr(asyncio, 'get_running_loop') else asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _create_status_page_sync, name, slug, title, description)
        return result

    except Exception as e:
        logger.error(f"Error occurred while creating status page '{name}': {str(e)}")
        raise

@mcp.tool()
async def edit_status_page(slug: str = Field(description="The slug of the status page to edit."),
                           options: dict = Field(description="Dictionary of status page attributes to update (e.g., name, title, description).")):
    """
    Edits an existing status page in Uptime Kuma.
    """
    try:
        api = await login_uptime_kuma()

        def _edit_status_page_sync(sp_slug, sp_options):
            try:
                logger.info(f"Attempting to edit status page with slug: {sp_slug} with options: {sp_options}")
                response = api.edit_status_page(slug=sp_slug, **sp_options)
                logger.info(f"Response for editing status page '{sp_slug}': {response}")
                if response.get("ok"):
                    return {"slug": sp_slug, "status": "success", "message": response.get("msg", "Status page edited successfully."), "response": response}
                else:
                    error_msg = response.get("msg", "Unknown error from API during status page edit")
                    logger.warning(f"Status page '{sp_slug}' possibly not edited. API response: {response}")
                    return {"slug": sp_slug, "status": "failed", "error_message": error_msg, "response": response}
            except Exception as e_sync:
                logger.error(f"Error editing status page with slug {sp_slug} (sync part): {str(e_sync)}")
                return {"slug": sp_slug, "status": "error", "error_message": str(e_sync)}

        loop = asyncio.get_running_loop() if hasattr(asyncio, 'get_running_loop') else asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _edit_status_page_sync, slug, options)
        return result

    except Exception as e:
        logger.error(f"Error occurred while editing status page with slug {slug}: {str(e)}")
        raise

@mcp.tool()
async def delete_status_page(slug: str = Field(description="The slug of the status page to delete.")):
    """
    Deletes a status page from Uptime Kuma.
    """
    try:
        api = await login_uptime_kuma()

        def _delete_status_page_sync(sp_slug):
            try:
                logger.info(f"Attempting to delete status page with slug: {sp_slug}")
                response = api.delete_status_page(slug=sp_slug)
                logger.info(f"Response for deleting status page '{sp_slug}': {response}")
                if response.get("ok"):
                    return {"slug": sp_slug, "status": "success", "message": response.get("msg", "Status page deleted successfully."), "response": response}
                else:
                    error_msg = response.get("msg", "Unknown error from API during status page deletion")
                    logger.warning(f"Status page '{sp_slug}' possibly not deleted. API response: {response}")
                    return {"slug": sp_slug, "status": "failed", "error_message": error_msg, "response": response}
            except Exception as e_sync:
                logger.error(f"Error deleting status page with slug {sp_slug} (sync part): {str(e_sync)}")
                return {"slug": sp_slug, "status": "error", "error_message": str(e_sync)}

        loop = asyncio.get_running_loop() if hasattr(asyncio, 'get_running_loop') else asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _delete_status_page_sync, slug)
        return result

    except Exception as e:
        logger.error(f"Error occurred while deleting status page with slug {slug}: {str(e)}")
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