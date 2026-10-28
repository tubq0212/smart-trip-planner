"""Exercise the real HelloAgents registry without network or model calls."""
import unittest
from unittest.mock import Mock, patch

from hello_agents.tools import MCPTool

from app.agents.trip_planner_agent import MultiAgentTripPlanner
from app.config import get_settings
from app.services import amap_service


def discovered_tools(tool):
    tool._available_tools = [
        {"name": "maps_text_search", "description": "Search places", "input_schema": {
            "type": "object", "properties": {
                "keywords": {"type": "string"}, "city": {"type": "string"}},
            "required": ["keywords"]}},
        {"name": "maps_weather", "description": "Query weather", "input_schema": {
            "type": "object", "properties": {"city": {"type": "string"}},
            "required": ["city"]}},
    ]


class AmapToolRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch.object(amap_service, "_amap_mcp_tool", None),
            patch.object(get_settings(), "amap_api_key", "test-key"),
        ]
        self.command_patch = patch.object(amap_service, "amap_server_command", return_value=["fake-server"])
        self.patches.append(self.command_patch)
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_discovery_failure_stops_before_llm_initialization(self):
        with patch.object(MCPTool, "_discover_tools"), patch(
            "app.services.llm_service.get_llm"
        ) as get_llm:
            with self.assertRaisesRegex(RuntimeError, "高德 MCP 工具未就绪"):
                MultiAgentTripPlanner()
        get_llm.assert_not_called()
        self.assertIsNone(amap_service._amap_mcp_tool)

    def test_missing_weather_is_not_accepted_as_ready(self):
        def partial(tool):
            discovered_tools(tool)
            tool._available_tools.pop()
        with patch.object(MCPTool, "_discover_tools", partial):
            with self.assertRaisesRegex(RuntimeError, "amap_maps_weather"):
                amap_service.get_amap_mcp_tool()
        self.assertIsNone(amap_service._amap_mcp_tool)

    def test_three_specialist_agents_register_and_execute_expanded_names(self):
        llm = Mock()
        with patch.object(MCPTool, "_discover_tools", discovered_tools), patch(
            "app.services.llm_service.get_llm", return_value=llm
        ):
            planner = MultiAgentTripPlanner()
        llm.invoke.assert_not_called()
        self.assertEqual(planner.planner_agent.list_tools(), [])
        for agent in (planner.attraction_agent, planner.weather_agent, planner.hotel_agent):
            self.assertTrue(amap_service.REQUIRED_AMAP_TOOLS.issubset(agent.list_tools()))
            with patch.object(planner.amap_tool, "run", return_value='{"ok": true}') as call:
                result = agent._execute_tool_call(
                    "amap_maps_text_search", "keywords=景点,city=厦门")
            self.assertNotIn("未找到工具", result)
            call.assert_called_once_with({"action": "call_tool", "tool_name": "maps_text_search",
                                          "arguments": {"keywords": "景点", "city": "厦门"}})
        with patch.object(planner.amap_tool, "run", return_value='{"weather": "晴"}') as call:
            result = planner.weather_agent._execute_tool_call("amap_maps_weather", "city=厦门")
        self.assertNotIn("未找到工具", result)
        call.assert_called_once_with({"action": "call_tool", "tool_name": "maps_weather",
                                      "arguments": {"city": "厦门"}})

    def test_real_agent_tool_loop_returns_tool_result_to_model(self):
        llm = Mock()
        llm.invoke.side_effect = ["[TOOL_CALL:amap_maps_weather:city=厦门]", "已取得天气信息"]
        with patch.object(MCPTool, "_discover_tools", discovered_tools), patch(
            "app.services.llm_service.get_llm", return_value=llm
        ):
            planner = MultiAgentTripPlanner()
        with patch.object(planner.amap_tool, "run", return_value='{"weather": "晴"}') as call:
            result = planner.weather_agent.run("查询厦门天气")
        self.assertEqual(result, "已取得天气信息")
        self.assertEqual(llm.invoke.call_count, 2)
        call.assert_called_once()
        messages = llm.invoke.call_args.args[0]
        self.assertTrue(any('"weather": "晴"' in item["content"] for item in messages))

    def test_launcher_prefers_preinstalled_isolated_tool(self):
        self.command_patch.stop()
        with patch("app.services.amap_service.shutil.which", return_value="/usr/local/bin/amap-mcp-server"):
            self.assertEqual(amap_service.amap_server_command(), ["/usr/local/bin/amap-mcp-server"])

    def test_uvx_fallback_uses_compatible_pins(self):
        self.command_patch.stop()
        with patch("app.services.amap_service.shutil.which", side_effect=[None, "/usr/bin/uvx"]):
            command = amap_service.amap_server_command()
        self.assertEqual(command, ["/usr/bin/uvx", *amap_service.AMAP_TOOL_REQUIREMENTS])


if __name__ == "__main__":
    unittest.main()
