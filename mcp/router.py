from tools.system.device_info import get_device_info
from tools.search.bing import bing_search


def dispatch(step: dict):
    """
    MCP Router:
    根据 capability 调用具体工具
    """
    capability = step.get("capability")

    if capability == "system_info":
        return get_device_info()

    if capability == "search":
        query = step.get("query", "")
        return bing_search(query)

    raise ValueError(f"Unknown capability: {capability}")
