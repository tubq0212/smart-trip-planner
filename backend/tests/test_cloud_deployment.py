import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.config import get_settings, validate_config
from app.agents.trip_planner_agent import MultiAgentTripPlanner
from app.models.schemas import TripRequest

class CloudDeploymentTests(unittest.TestCase):
    def test_fast_mode_starts_without_map_key(self):
        with patch.dict(os.environ, {'TRIP_FAST_MODE':'true'}), patch.object(get_settings(),'amap_api_key',''):
            self.assertTrue(validate_config())

    def test_no_key_plan_uses_real_curated_places_without_weather(self):
        request=TripRequest(city='厦门',start_date='2026-11-06',end_date='2026-11-08',
                            travel_days=3,transportation='公共交通',accommodation='经济型酒店')
        planner=MultiAgentTripPlanner.__new__(MultiAgentTripPlanner)
        with patch.object(get_settings(),'amap_api_key',''), patch.object(planner,'_amap_search_places',side_effect=AssertionError('No external query expected')):
            plan=planner._create_amap_direct_plan(request)
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.days),3)
        self.assertIn('鼓浪屿',[x.name for x in plan.days[0].attractions])
        self.assertEqual(plan.weather_info,[])

    def test_client_configuration_does_not_include_server_secrets(self):
        from cloud_app import app
        with patch.dict(os.environ,{'AMAP_WEB_JS_KEY':'browser-example','AMAP_API_KEY':'server-example','LLM_API_KEY':'private-example'}):
            response=TestClient(app).get('/api/client-config')
        self.assertEqual(response.json(),{'amap_web_js_key':'browser-example'})
