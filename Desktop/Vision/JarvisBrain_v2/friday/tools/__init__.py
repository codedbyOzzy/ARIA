"""Tool registry."""

from friday.tools import desktop_control, local_llm, memory, ollama_runtime, policy, system, task_executor, utils, weather, web


def register_all_tools(mcp) -> None:
    web.register(mcp)
    policy.register(mcp)
    memory.register(mcp)
    ollama_runtime.register(mcp)
    system.register(mcp)
    utils.register(mcp)
    local_llm.register(mcp)
    desktop_control.register(mcp)
    task_executor.register(mcp)
    weather.register(mcp)
