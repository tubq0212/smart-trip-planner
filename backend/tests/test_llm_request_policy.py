"""Validate waiting and retry policy without provider requests."""
import os
import unittest
from unittest.mock import Mock, patch

from app.services import llm_service
from app.agents.trip_planner_agent import MultiAgentTripPlanner
from app.models.schemas import TripRequest


class LlmRequestPolicyTests(unittest.TestCase):
    def test_client_has_explicit_timeout_and_no_automatic_retries(self):
        fake = Mock()
        original_client = fake._client
        with patch.dict(os.environ, {"LLM_TIMEOUT": "90"}), patch.object(
            llm_service, "_llm_instance", None
        ), patch.object(llm_service, "HelloAgentsLLM", return_value=fake) as create:
            client = llm_service.get_llm()
            self.assertIs(llm_service.get_llm(), client)
        create.assert_called_once_with(timeout=90.0)
        original_client.with_options.assert_called_once_with(max_retries=0)
        self.assertIs(client._client, original_client.with_options.return_value)

    def test_four_stages_remain_and_final_generation_gets_longer_timeout(self):
        planner = MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
        order = []
        for name in ("attraction_agent", "weather_agent", "hotel_agent", "planner_agent"):
            agent = Mock()
            agent.run.side_effect = lambda *args, stage=name, **kwargs: order.append(stage) or "result"
            setattr(planner, name, agent)
        expected = Mock()
        request = TripRequest(city="厦门", start_date="2026-11-01", end_date="2026-11-01",
                              travel_days=1, transportation="公共交通", accommodation="经济型酒店")
        with patch.object(planner, "_parse_response", return_value=expected):
            result = planner.plan_trip(request)
        self.assertIs(result, expected)
        self.assertEqual(order, ["attraction_agent", "weather_agent", "hotel_agent", "planner_agent"])
        self.assertEqual(planner.planner_agent.run.call_args.kwargs, {"timeout": 120.0})


if __name__ == "__main__":
    unittest.main()
