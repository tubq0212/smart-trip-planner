"""多智能体旅行规划系统"""

import json
import math
import os
import random
import urllib.parse
import urllib.request
from typing import Dict, Any, List
from ..models.schemas import TripRequest, TripPlan, DayPlan, Attraction, Meal, WeatherInfo, Location, Hotel, Budget, RouteSegment
from ..config import get_settings

# ============ Agent提示词 ============

ATTRACTION_AGENT_PROMPT = """你是景点搜索专家。你的任务是根据城市和用户偏好搜索合适的景点。

**重要提示:**
你必须使用工具来搜索景点!不要自己编造景点信息!

**工具调用格式:**
使用maps_text_search工具时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_text_search:keywords=景点关键词,city=城市名]`

**示例:**
用户: "搜索北京的历史文化景点"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=历史文化,city=北京]

用户: "搜索上海的公园"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=公园,city=上海]

**注意:**
1. 必须使用工具,不要直接回答
2. 格式必须完全正确,包括方括号和冒号
3. 参数用逗号分隔
"""

WEATHER_AGENT_PROMPT = """你是天气查询专家。你的任务是查询指定城市的天气信息。

**重要提示:**
你必须使用工具来查询天气!不要自己编造天气信息!

**工具调用格式:**
使用maps_weather工具时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_weather:city=城市名]`

**示例:**
用户: "查询北京天气"
你的回复: [TOOL_CALL:amap_maps_weather:city=北京]

用户: "上海的天气怎么样"
你的回复: [TOOL_CALL:amap_maps_weather:city=上海]

**注意:**
1. 必须使用工具,不要直接回答
2. 格式必须完全正确,包括方括号和冒号
"""

HOTEL_AGENT_PROMPT = """你是酒店推荐专家。你的任务是根据城市和景点位置推荐合适的酒店。

**重要提示:**
你必须使用工具来搜索酒店!不要自己编造酒店信息!

**工具调用格式:**
使用maps_text_search工具搜索酒店时,必须严格按照以下格式:
`[TOOL_CALL:amap_maps_text_search:keywords=酒店,city=城市名]`

**示例:**
用户: "搜索北京的酒店"
你的回复: [TOOL_CALL:amap_maps_text_search:keywords=酒店,city=北京]

**注意:**
1. 必须使用工具,不要直接回答
2. 格式必须完全正确,包括方括号和冒号
3. 关键词使用"酒店"或"宾馆"
"""

PLANNER_AGENT_PROMPT = """你是行程规划专家。你的任务是根据景点信息和天气信息,生成详细的旅行计划。

请严格按照以下JSON格式返回旅行计划:
```json
{
  "city": "城市名称",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "days": [
    {
      "date": "YYYY-MM-DD",
      "day_index": 0,
      "description": "第1天行程概述",
      "transportation": "交通方式",
      "accommodation": "住宿类型",
      "hotel": {
        "name": "酒店名称",
        "address": "酒店地址",
        "location": {"longitude": 116.397128, "latitude": 39.916527},
        "price_range": "300-500元",
        "rating": "4.5",
        "distance": "距离景点2公里",
        "type": "经济型酒店",
        "estimated_cost": 400
      },
      "attractions": [
        {
          "name": "景点名称",
          "address": "详细地址",
          "location": {"longitude": 116.397128, "latitude": 39.916527},
          "visit_duration": 120,
          "description": "景点详细描述",
          "category": "景点类别",
          "ticket_price": 60
        }
      ],
      "meals": [
        {"type": "breakfast", "name": "早餐推荐", "description": "早餐描述", "estimated_cost": 30},
        {"type": "lunch", "name": "午餐推荐", "description": "午餐描述", "estimated_cost": 50},
        {"type": "dinner", "name": "晚餐推荐", "description": "晚餐描述", "estimated_cost": 80}
      ]
    }
  ],
  "weather_info": [
    {
      "date": "YYYY-MM-DD",
      "day_weather": "晴",
      "night_weather": "多云",
      "day_temp": 25,
      "night_temp": 15,
      "wind_direction": "南风",
      "wind_power": "1-3级"
    }
  ],
  "overall_suggestions": "总体建议",
  "budget": {
    "total_attractions": 180,
    "total_hotels": 1200,
    "total_meals": 480,
    "total_transportation": 200,
    "total": 2060
  }
}
```

**重要提示:**
1. weather_info数组必须包含每一天的天气信息
2. 温度必须是纯数字(不要带°C等单位)
3. 每天安排2-3个景点
4. 考虑景点之间的距离和游览时间
5. 每天必须包含早中晚三餐
6. 提供实用的旅行建议
7. **必须包含预算信息**:
   - 景点门票价格(ticket_price)
   - 餐饮预估费用(estimated_cost)
   - 酒店预估费用(estimated_cost)
   - 预算汇总(budget)包含各项总费用
"""


class MultiAgentTripPlanner:
    """多智能体旅行规划系统"""

    def __init__(self):
        """初始化多智能体系统"""
        from hello_agents import SimpleAgent
        from hello_agents.tools import MCPTool
        from ..services.llm_service import get_llm
        print("🔄 开始初始化多智能体旅行规划系统...")

        try:
            settings = get_settings()
            self.llm = get_llm()

            # 创建共享的MCP工具(只创建一次)
            print("  - 创建共享MCP工具...")
            self.amap_tool = MCPTool(
                name="amap",
                description="高德地图服务",
                server_command=["uvx", "amap-mcp-server"],
                env={"AMAP_MAPS_API_KEY": settings.amap_api_key},
                auto_expand=True
            )
            self.amap_tool.expandable=True

            # 创建景点搜索Agent
            print("  - 创建景点搜索Agent...")
            self.attraction_agent = SimpleAgent(
                name="景点搜索专家",
                llm=self.llm,
                system_prompt=ATTRACTION_AGENT_PROMPT
            )
            self.attraction_agent.add_tool(self.amap_tool)

            # 创建天气查询Agent
            print("  - 创建天气查询Agent...")
            self.weather_agent = SimpleAgent(
                name="天气查询专家",
                llm=self.llm,
                system_prompt=WEATHER_AGENT_PROMPT
            )
            self.weather_agent.add_tool(self.amap_tool)

            # 创建酒店推荐Agent
            print("  - 创建酒店推荐Agent...")
            self.hotel_agent = SimpleAgent(
                name="酒店推荐专家",
                llm=self.llm,
                system_prompt=HOTEL_AGENT_PROMPT
            )
            self.hotel_agent.add_tool(self.amap_tool)

            # 创建行程规划Agent(不需要工具)
            print("  - 创建行程规划Agent...")
            self.planner_agent = SimpleAgent(
                name="行程规划专家",
                llm=self.llm,
                system_prompt=PLANNER_AGENT_PROMPT
            )

            print(f"✅ 多智能体系统初始化成功")
            print(f"   景点搜索Agent: {len(self.attraction_agent.list_tools())} 个工具")
            print(f"   天气查询Agent: {len(self.weather_agent.list_tools())} 个工具")
            print(f"   酒店推荐Agent: {len(self.hotel_agent.list_tools())} 个工具")

        except Exception as e:
            print(f"❌ 多智能体系统初始化失败: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def plan_trip(self, request: TripRequest) -> TripPlan:
        """
        使用多智能体协作生成旅行计划

        Args:
            request: 旅行请求

        Returns:
            旅行计划
        """
        try:
            print(f"\n{'='*60}")
            print(f"🚀 开始多智能体协作规划旅行...")
            print(f"目的地: {request.city}")
            print(f"日期: {request.start_date} 至 {request.end_date}")
            print(f"天数: {request.travel_days}天")
            print(f"偏好: {', '.join(request.preferences) if request.preferences else '无'}")
            print(f"{'='*60}\n")

            # 步骤1: 景点搜索Agent搜索景点
            print("📍 步骤1: 搜索景点...")
            attraction_query = self._build_attraction_query(request)
            attraction_response = self.attraction_agent.run(attraction_query)
            print(f"景点搜索结果: {attraction_response[:200]}...\n")

            # 步骤2: 天气查询Agent查询天气
            print("🌤️  步骤2: 查询天气...")
            weather_query = f"请查询{request.city}的天气信息"
            weather_response = self.weather_agent.run(weather_query)
            print(f"天气查询结果: {weather_response[:200]}...\n")

            # 步骤3: 酒店推荐Agent搜索酒店
            print("🏨 步骤3: 搜索酒店...")
            hotel_query = f"请搜索{request.city}的{request.accommodation}酒店"
            hotel_response = self.hotel_agent.run(hotel_query)
            print(f"酒店搜索结果: {hotel_response[:200]}...\n")

            # 步骤4: 行程规划Agent整合信息生成计划
            print("📋 步骤4: 生成行程计划...")
            planner_query = self._build_planner_query(request, attraction_response, weather_response, hotel_response)
            planner_response = self.planner_agent.run(planner_query)
            print(f"行程规划结果: {planner_response[:300]}...\n")

            # 解析最终计划
            trip_plan = self._parse_response(planner_response, request)

            print(f"{'='*60}")
            print(f"✅ 旅行计划生成完成!")
            print(f"{'='*60}\n")

            return trip_plan

        except Exception as e:
            print(f"❌ 生成旅行计划失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return self._create_fallback_plan(request)
    
    def _build_attraction_query(self, request: TripRequest) -> str:
        """构建景点搜索查询 - 直接包含工具调用"""
        keywords = []
        if request.preferences:
            # 只取第一个偏好作为关键词
            keywords = request.preferences[0]
        else:
            keywords = "景点"

        # 直接返回工具调用格式
        query = f"请使用amap_maps_text_search工具搜索{request.city}的{keywords}相关景点。\n[TOOL_CALL:amap_maps_text_search:keywords={keywords},city={request.city}]"
        return query

    def _build_planner_query(self, request: TripRequest, attractions: str, weather: str, hotels: str = "") -> str:
        """构建行程规划查询"""
        query = f"""请根据以下信息生成{request.city}的{request.travel_days}天旅行计划:

**基本信息:**
- 城市: {request.city}
- 日期: {request.start_date} 至 {request.end_date}
- 天数: {request.travel_days}天
- 交通方式: {request.transportation}
- 住宿: {request.accommodation}
- 偏好: {', '.join(request.preferences) if request.preferences else '无'}

**景点信息:**
{attractions}

**天气信息:**
{weather}

**酒店信息:**
{hotels}

**要求:**
1. 每天安排2-3个景点
2. 每天必须包含早中晚三餐
3. 每天推荐一个具体的酒店(从酒店信息中选择)
3. 考虑景点之间的距离和交通方式
4. 返回完整的JSON格式数据
5. 景点的经纬度坐标要真实准确
"""
        if request.free_text_input:
            query += f"\n**额外要求:** {request.free_text_input}"

        return query
    
    def _parse_response(self, response: str, request: TripRequest) -> TripPlan:
        """
        解析Agent响应
        
        Args:
            response: Agent响应文本
            request: 原始请求
            
        Returns:
            旅行计划
        """
        try:
            # 尝试从响应中提取JSON
            # 查找JSON代码块
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                json_str = response[json_start:json_end].strip()
            elif "{" in response and "}" in response:
                # 直接查找JSON对象
                json_start = response.find("{")
                json_end = response.rfind("}") + 1
                json_str = response[json_start:json_end]
            else:
                raise ValueError("响应中未找到JSON数据")
            
            # 解析JSON
            data = json.loads(json_str)
            
            # 转换为TripPlan对象
            trip_plan = TripPlan(**data)
            
            return trip_plan
            
        except Exception as e:
            print(f"⚠️  解析响应失败: {str(e)}")
            print(f"   将使用备用方案生成计划")
            return self._create_fallback_plan(request)
    
    def _create_fallback_plan(self, request: TripRequest) -> TripPlan:
        """创建备用计划(当Agent失败时)"""
        direct_plan = self._create_amap_direct_plan(request)
        if direct_plan is not None:
            return direct_plan

        from datetime import datetime, timedelta
        
        # 解析日期
        start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
        
        # 创建每日行程
        days = []
        for i in range(request.travel_days):
            current_date = start_date + timedelta(days=i)
            
            day_plan = DayPlan(
                date=current_date.strftime("%Y-%m-%d"),
                day_index=i,
                description=f"第{i+1}天行程",
                transportation=request.transportation,
                accommodation=request.accommodation,
                attractions=[
                    Attraction(
                        name=f"{request.city}景点{j+1}",
                        address=f"{request.city}市",
                        location=Location(longitude=116.4 + i*0.01 + j*0.005, latitude=39.9 + i*0.01 + j*0.005),
                        visit_duration=120,
                        description=f"这是{request.city}的著名景点",
                        category="景点"
                    )
                    for j in range(2)
                ],
                meals=[
                    Meal(type="breakfast", name=f"第{i+1}天早餐", description="当地特色早餐"),
                    Meal(type="lunch", name=f"第{i+1}天午餐", description="午餐推荐"),
                    Meal(type="dinner", name=f"第{i+1}天晚餐", description="晚餐推荐")
                ]
            )
            days.append(day_plan)
        
        return TripPlan(
            city=request.city,
            start_date=request.start_date,
            end_date=request.end_date,
            days=days,
            weather_info=[],
            overall_suggestions=f"这是为您规划的{request.city}{request.travel_days}日游行程,建议提前查看各景点的开放时间。"
        )


# 全局多智能体系统实例
    def _create_amap_direct_plan(self, request: TripRequest) -> TripPlan | None:
        """Build a usable plan from AMap Web API when MCP/LLM is slow or unavailable."""
        try:
            from datetime import datetime, timedelta

            settings = get_settings()
            online = bool(settings.amap_api_key)
            pois = self._amap_search_places(request.city, request.preferences) if online else []
            if not pois:
                print("AMap direct fallback did not find POIs; using built-in placeholder plan.")
                pois = self._curated_city_pois(request.city)
            if not pois:
                return None

            try:
                hotels = self._amap_search_keyword(request.city, request.accommodation or "hotel") if online else []
            except Exception as exc:
                print(f"AMap hotel search failed: {exc}")
                hotels = []
            if not hotels:
                hotels = self._curated_city_hotels(request.city)

            try:
                restaurants = self._amap_search_keyword(request.city, "美食 餐厅") if online else []
            except Exception as exc:
                print(f"AMap restaurant search failed: {exc}")
                restaurants = []
            if not restaurants:
                restaurants = self._curated_city_restaurants(request.city)

            weather = self._amap_weather(request.city) if online else {}
            start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
            spots_per_day = 3 if len(pois) >= request.travel_days * 3 else 2
            days = []

            for day_index in range(request.travel_days):
                current_date = start_date + timedelta(days=day_index)
                day_pois = [
                    pois[(day_index * spots_per_day + offset) % len(pois)]
                    for offset in range(spots_per_day)
                ]
                hotel = None
                if hotels:
                    hotel_poi = hotels[day_index % len(hotels)]
                    hotel = self._poi_to_hotel(hotel_poi, request.accommodation)

                attractions = [self._poi_to_attraction(poi, offset) for offset, poi in enumerate(day_pois)]
                route_segments = self._build_route_segments(attractions, request.transportation)
                meals = self._build_daily_meals(request.city, restaurants, day_index)

                days.append(DayPlan(
                    date=current_date.strftime("%Y-%m-%d"),
                    day_index=day_index,
                    description=f"第{day_index + 1}天：{request.city}精选路线",
                    transportation=request.transportation,
                    accommodation=request.accommodation,
                    hotel=hotel,
                    attractions=attractions,
                    route_segments=route_segments,
                    meals=meals,
                ))

            weather_info = []
            for day_index in range(request.travel_days) if weather else []:
                current_date = start_date + timedelta(days=day_index)
                weather_info.append(WeatherInfo(
                    date=current_date.strftime("%Y-%m-%d"),
                    day_weather=weather.get("dayweather", "多云"),
                    night_weather=weather.get("nightweather", weather.get("dayweather", "多云")),
                    day_temp=self._safe_int(weather.get("daytemp"), 28),
                    night_temp=self._safe_int(weather.get("nighttemp"), 22),
                    wind_direction=weather.get("daywind", ""),
                    wind_power=weather.get("daypower", ""),
                ))

            attraction_cost = sum(a.ticket_price for d in days for a in d.attractions)
            hotel_cost = sum((d.hotel.estimated_cost if d.hotel else 300) for d in days)
            meal_cost = sum(m.estimated_cost for d in days for m in d.meals)
            transport_cost = request.travel_days * 60

            return TripPlan(
                city=request.city,
                start_date=request.start_date,
                end_date=request.end_date,
                days=days,
                weather_info=weather_info,
                overall_suggestions="当前为快速规划模式，使用地图查询或内置城市资料，未调用大模型。预算与交通时间为估算，出行前请确认开放时间和预约要求。",
                budget=Budget(
                    total_attractions=attraction_cost,
                    total_hotels=hotel_cost,
                    total_meals=meal_cost,
                    total_transportation=transport_cost,
                    total=attraction_cost + hotel_cost + meal_cost + transport_cost,
                ),
            )
        except Exception as exc:
            print(f"AMap direct fallback failed: {exc}")
            return None

    def _amap_search_places(self, city: str, preferences: List[str]) -> List[Dict[str, Any]]:
        keywords = list(preferences or []) + ["景点", "公园", "博物馆", "美食街"]
        seen = set()
        results = []
        for keyword in keywords:
            try:
                keyword_pois = self._amap_search_keyword(city, keyword)
            except Exception as exc:
                print(f"AMap POI search error for {keyword}: {exc}")
                continue
            for poi in keyword_pois:
                poi_id = poi.get("id") or poi.get("name")
                if not poi.get("name") or poi_id in seen:
                    continue
                seen.add(poi_id)
                results.append(poi)
                if len(results) >= 30:
                    return results
        return results

    def _amap_search_keyword(self, city: str, keyword: str) -> List[Dict[str, Any]]:
        settings = get_settings()
        params = urllib.parse.urlencode({
            "key": settings.amap_api_key,
            "keywords": keyword,
            "city": city,
            "citylimit": "true",
            "offset": 20,
            "page": 1,
            "extensions": "all",
        })
        url = f"https://restapi.amap.com/v3/place/text?{params}"
        with urllib.request.urlopen(url, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
        if data.get("status") != "1":
            print(f"AMap POI search failed for {keyword}: {data.get('info')}")
            return []
        return data.get("pois", [])

    def _amap_weather(self, city: str) -> Dict[str, Any]:
        try:
            settings = get_settings()
            params = urllib.parse.urlencode({
                "key": settings.amap_api_key,
                "city": city,
                "extensions": "base",
            })
            url = f"https://restapi.amap.com/v3/weather/weatherInfo?{params}"
            with urllib.request.urlopen(url, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))
            if data.get("status") == "1" and data.get("lives"):
                return data["lives"][0]
        except Exception as exc:
            print(f"AMap weather fallback failed: {exc}")
        return {}

    def _poi_to_attraction(self, poi: Dict[str, Any], offset: int) -> Attraction:
        type_name = (poi.get("type") or "景点").split(";")[0]
        return Attraction(
            name=poi.get("name", "景点"),
            address=poi.get("address") or poi.get("adname") or "",
            location=self._location_from_poi(poi) or Location(longitude=118.0894, latitude=24.4798),
            visit_duration=[90, 120, 150][offset % 3],
            description=f"{type_name}，来自高德地图POI搜索结果。",
            category=type_name,
            rating=self._safe_float(poi.get("biz_ext", {}).get("rating") if isinstance(poi.get("biz_ext"), dict) else None),
            photos=[p.get("url") for p in poi.get("photos", []) if p.get("url")][:3],
            poi_id=poi.get("id", ""),
            image_url=(poi.get("photos") or [{}])[0].get("url"),
            ticket_price=0,
        )

    def _poi_to_hotel(self, poi: Dict[str, Any], accommodation: str) -> Hotel:
        biz_ext = poi.get("biz_ext") if isinstance(poi.get("biz_ext"), dict) else {}
        return Hotel(
            name=poi.get("name", "推荐酒店"),
            address=poi.get("address") or poi.get("adname") or "",
            location=self._location_from_poi(poi),
            price_range=str(biz_ext.get("cost") or "200-500"),
            rating=str(biz_ext.get("rating") or ""),
            distance="建议选择当日景点通勤便利区域",
            type=accommodation or (poi.get("type") or "酒店").split(";")[0],
            estimated_cost=self._safe_int(biz_ext.get("cost"), 300),
        )

    def _build_daily_meals(self, city: str, restaurants: List[Dict[str, Any]], day_index: int) -> List[Meal]:
        if not restaurants:
            restaurants = self._curated_city_restaurants(city)

        meal_types = [
            ("breakfast", "早餐", 25),
            ("lunch", "午餐", 60),
            ("dinner", "晚餐", 80),
        ]
        meals: List[Meal] = []
        for offset, (meal_type, label, default_cost) in enumerate(meal_types):
            poi = restaurants[(day_index * len(meal_types) + offset) % len(restaurants)]
            meals.append(self._poi_to_meal(poi, meal_type, label, default_cost))
        return meals

    def _poi_to_meal(self, poi: Dict[str, Any], meal_type: str, label: str, default_cost: int) -> Meal:
        biz_ext = poi.get("biz_ext") if isinstance(poi.get("biz_ext"), dict) else {}
        type_name = (poi.get("type") or "餐饮").split(";")[0]
        cost = self._safe_int(biz_ext.get("cost"), default_cost)
        return Meal(
            type=meal_type,
            name=poi.get("name", f"推荐{label}"),
            address=poi.get("address") or poi.get("adname") or "",
            location=self._location_from_poi(poi),
            description=f"{label}推荐，类型：{type_name}",
            estimated_cost=cost,
        )

    def _curated_city_pois(self, city: str) -> List[Dict[str, Any]]:
        city_pois = {
            "厦门": [
                ("鼓浪屿", "厦门市思明区鼓浪屿", "118.067786,24.444651", "风景名胜"),
                ("厦门大学", "厦门市思明区思明南路422号", "118.100869,24.437795", "科教文化"),
                ("南普陀寺", "厦门市思明区思明南路515号", "118.103886,24.443052", "风景名胜"),
                ("环岛路", "厦门市思明区环岛南路", "118.150824,24.434746", "风景名胜"),
                ("曾厝垵", "厦门市思明区曾厝垵社", "118.131578,24.429173", "休闲街区"),
                ("沙坡尾艺术西区", "厦门市思明区沙坡尾", "118.090641,24.442448", "文化艺术"),
                ("中山路步行街", "厦门市思明区中山路", "118.080578,24.456137", "商业街"),
                ("集美学村", "厦门市集美区银江路", "118.098518,24.570479", "风景名胜"),
                ("园林植物园", "厦门市思明区虎园路25号", "118.111626,24.451286", "公园广场"),
            ],
            "北京": [
                ("故宫博物院", "北京市东城区景山前街4号", "116.397026,39.918058", "风景名胜"),
                ("天坛公园", "北京市东城区天坛东里甲1号", "116.410886,39.882569", "风景名胜"),
                ("颐和园", "北京市海淀区新建宫门路19号", "116.275505,39.999715", "风景名胜"),
            ],
            "上海": [
                ("外滩", "上海市黄浦区中山东一路", "121.490317,31.241701", "风景名胜"),
                ("上海博物馆", "上海市黄浦区人民大道201号", "121.475422,31.228829", "博物馆"),
                ("武康路", "上海市徐汇区武康路", "121.440705,31.211933", "休闲街区"),
            ],
            "杭州": [
                ("西湖", "杭州市西湖区龙井路1号", "120.141482,30.246129", "风景名胜"),
                ("灵隐寺", "杭州市西湖区法云弄1号", "120.101406,30.240826", "风景名胜"),
                ("西溪国家湿地公园", "杭州市西湖区天目山路518号", "120.063239,30.267749", "公园广场"),
            ],
            "成都": [
                ("武侯祠", "成都市武侯区武侯祠大街231号", "104.048425,30.647118", "风景名胜"),
                ("宽窄巷子", "成都市青羊区长顺上街", "104.055145,30.673004", "休闲街区"),
                ("成都大熊猫繁育研究基地", "成都市成华区熊猫大道1375号", "104.145533,30.735903", "风景名胜"),
            ],
            "广州": [
                ("陈家祠", "广州市荔湾区中山七路", "113.246536,23.131279", "风景名胜"),
                ("沙面岛", "广州市荔湾区沙面", "113.238003,23.109037", "风景名胜"),
                ("广州塔", "广州市海珠区阅江西路222号", "113.330934,23.113401", "风景名胜"),
            ],
        }
        items = city_pois.get(city, [])
        return [
            {
                "id": f"curated-{city}-{index}",
                "name": name,
                "address": address,
                "location": location,
                "type": type_name,
                "photos": [],
            }
            for index, (name, address, location, type_name) in enumerate(items)
        ]

    def _curated_city_hotels(self, city: str) -> List[Dict[str, Any]]:
        city_hotels = {
            "厦门": [
                ("全季酒店(厦门中山路店)", "厦门市思明区中山路步行街附近", "118.081014,24.455305", "经济型酒店", 320, "4.6"),
                ("厦门宾馆", "厦门市思明区虎园路16号", "118.102316,24.453021", "舒适型酒店", 420, "4.7"),
                ("厦门海景千禧大酒店", "厦门市思明区镇海路12号", "118.081683,24.449313", "高端酒店", 680, "4.6"),
            ],
            "北京": [
                ("北京饭店", "北京市东城区东长安街33号", "116.408643,39.908637", "高端酒店", 780, "4.7"),
                ("全季酒店(北京天安门店)", "北京市东城区前门区域", "116.397827,39.899811", "经济型酒店", 420, "4.5"),
                ("北京王府井希尔顿酒店", "北京市东城区王府井东街8号", "116.414876,39.915392", "高端酒店", 980, "4.7"),
            ],
            "上海": [
                ("全季酒店(上海外滩店)", "上海市黄浦区外滩区域", "121.488595,31.237364", "经济型酒店", 450, "4.5"),
                ("上海和平饭店", "上海市黄浦区南京东路20号", "121.490709,31.239515", "高端酒店", 1280, "4.8"),
                ("上海锦江饭店", "上海市黄浦区茂名南路59号", "121.459559,31.221296", "高端酒店", 850, "4.7"),
            ],
            "杭州": [
                ("杭州西湖国宾馆", "杭州市西湖区杨公堤18号", "120.135515,30.236671", "高端酒店", 980, "4.8"),
                ("全季酒店(杭州西湖湖滨店)", "杭州市上城区湖滨商圈", "120.164964,30.253018", "经济型酒店", 420, "4.6"),
                ("杭州索菲特西湖大酒店", "杭州市上城区西湖大道333号", "120.165796,30.245879", "高端酒店", 760, "4.6"),
            ],
            "成都": [
                ("成都博舍", "成都市锦江区笔帖式街81号", "104.083126,30.655918", "高端酒店", 1180, "4.8"),
                ("全季酒店(成都春熙路店)", "成都市锦江区春熙路商圈", "104.080999,30.657399", "经济型酒店", 360, "4.6"),
                ("成都总府皇冠假日酒店", "成都市锦江区总府街31号", "104.079338,30.662612", "舒适型酒店", 580, "4.6"),
            ],
            "广州": [
                ("广州白天鹅宾馆", "广州市荔湾区沙面南街1号", "113.238696,23.108476", "高端酒店", 980, "4.8"),
                ("全季酒店(广州北京路店)", "广州市越秀区北京路商圈", "113.268954,23.124847", "经济型酒店", 380, "4.5"),
                ("广州花园酒店", "广州市越秀区环市东路368号", "113.284151,23.136927", "高端酒店", 760, "4.7"),
            ],
        }
        return self._curated_lodging_or_food(city, city_hotels)

    def _curated_city_restaurants(self, city: str) -> List[Dict[str, Any]]:
        city_restaurants = {
            "厦门": [
                ("黄则和花生汤店(中山路店)", "厦门市思明区中山路22-24号", "118.081592,24.455362", "餐饮服务;中餐厅", 25, "4.4"),
                ("八婆婆烧仙草(轮渡店)", "厦门市思明区太平路22号", "118.077879,24.454034", "餐饮服务;甜品店", 18, "4.5"),
                ("临家闽南菜(环岛路店)", "厦门市思明区环岛南路", "118.151210,24.434212", "餐饮服务;福建菜", 90, "4.6"),
                ("佳味再添小吃店", "厦门市思明区大同路49号", "118.082683,24.457961", "餐饮服务;小吃", 35, "4.3"),
                ("宴遇福建菜", "厦门市思明区中华城附近", "118.083913,24.454815", "餐饮服务;福建菜", 120, "4.6"),
                ("1980烧肉粽", "厦门市思明区中山路353号", "118.083675,24.455477", "餐饮服务;小吃", 30, "4.4"),
            ],
            "北京": [
                ("庆丰包子铺(前门店)", "北京市东城区前门大街附近", "116.397501,39.899015", "餐饮服务;小吃", 25, "4.3"),
                ("四季民福烤鸭店(故宫店)", "北京市东城区南池子大街11号", "116.403873,39.916145", "餐饮服务;北京菜", 130, "4.7"),
                ("东来顺饭庄(王府井店)", "北京市东城区王府井大街", "116.411903,39.914722", "餐饮服务;火锅", 120, "4.5"),
            ],
            "上海": [
                ("小杨生煎(南京东路店)", "上海市黄浦区南京东路附近", "121.480711,31.235172", "餐饮服务;小吃", 30, "4.4"),
                ("德兴馆(广东路店)", "上海市黄浦区广东路471号", "121.481107,31.232121", "餐饮服务;本帮菜", 80, "4.5"),
                ("绿波廊", "上海市黄浦区豫园路115号", "121.492024,31.227431", "餐饮服务;本帮菜", 150, "4.6"),
            ],
            "杭州": [
                ("知味观(湖滨店)", "杭州市上城区仁和路83号", "120.164045,30.255087", "餐饮服务;小吃", 35, "4.4"),
                ("外婆家(湖滨店)", "杭州市上城区湖滨商圈", "120.164749,30.252676", "餐饮服务;杭帮菜", 80, "4.5"),
                ("楼外楼", "杭州市西湖区孤山路30号", "120.148522,30.254681", "餐饮服务;杭帮菜", 160, "4.5"),
            ],
            "成都": [
                ("龙抄手(春熙路店)", "成都市锦江区春熙路商圈", "104.080856,30.657054", "餐饮服务;小吃", 28, "4.4"),
                ("陈麻婆豆腐(骡马市店)", "成都市青羊区西玉龙街197号", "104.066021,30.668182", "餐饮服务;川菜", 80, "4.5"),
                ("蜀大侠火锅(春熙路店)", "成都市锦江区春熙路商圈", "104.081850,30.655913", "餐饮服务;火锅", 130, "4.6"),
            ],
            "广州": [
                ("点都德(北京路店)", "广州市越秀区北京路商圈", "113.269501,23.125166", "餐饮服务;粤菜", 85, "4.6"),
                ("银记肠粉店(文昌店)", "广州市荔湾区文昌北路", "113.250010,23.120532", "餐饮服务;小吃", 25, "4.4"),
                ("陶陶居酒家(第十甫路店)", "广州市荔湾区第十甫路20号", "113.248756,23.115001", "餐饮服务;粤菜", 120, "4.6"),
            ],
        }
        return self._curated_lodging_or_food(city, city_restaurants)

    def _curated_lodging_or_food(self, city: str, data: Dict[str, List[tuple]]) -> List[Dict[str, Any]]:
        items = data.get(city, [])
        return [
            {
                "id": f"curated-extra-{city}-{index}",
                "name": name,
                "address": address,
                "location": location,
                "type": type_name,
                "biz_ext": {"cost": cost, "rating": rating},
                "photos": [],
            }
            for index, (name, address, location, type_name, cost, rating) in enumerate(items)
        ]

    def _location_from_poi(self, poi: Dict[str, Any]) -> Location | None:
        location = poi.get("location")
        if not location or "," not in location:
            return None
        longitude, latitude = location.split(",", 1)
        return Location(longitude=float(longitude), latitude=float(latitude))

    def _safe_int(self, value: Any, default: int) -> int:
        try:
            return int(float(value))
        except Exception:
            return default

    def _build_route_segments(self, attractions: List[Attraction], transportation: str) -> List[RouteSegment]:
        segments: List[RouteSegment] = []
        for origin, destination in zip(attractions, attractions[1:]):
            distance_km = self._haversine_km(
                origin.location.longitude,
                origin.location.latitude,
                destination.location.longitude,
                destination.location.latitude,
            )
            speed_kmh = self._transport_speed_kmh(transportation)
            duration_minutes = max(5, round(distance_km / speed_kmh * 60))
            segments.append(
                RouteSegment(
                    from_name=origin.name,
                    to_name=destination.name,
                    distance_km=round(distance_km, 2),
                    duration_minutes=duration_minutes,
                    transportation=transportation,
                    description=self._format_route_description(origin.name, destination.name, transportation),
                )
            )
        return segments

    def _transport_speed_kmh(self, transportation: str) -> float:
        mode = (transportation or "").lower()
        if any(keyword in mode for keyword in ["walking", "walk", "步行"]):
            return 4.5
        if any(keyword in mode for keyword in ["driving", "drive", "自驾", "驾车", "打车", "出租"]):
            return 28.0
        if any(keyword in mode for keyword in ["bicycle", "bike", "cycling", "骑行"]):
            return 12.0
        if any(keyword in mode for keyword in ["transit", "bus", "metro", "公交", "地铁", "公共交通"]):
            return 18.0
        return 15.0

    def _haversine_km(self, lon1: float, lat1: float, lon2: float, lat2: float) -> float:
        earth_radius_km = 6371.0
        lon1_rad, lat1_rad, lon2_rad, lat2_rad = map(math.radians, [lon1, lat1, lon2, lat2])
        delta_lon = lon2_rad - lon1_rad
        delta_lat = lat2_rad - lat1_rad
        value = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
        )
        return earth_radius_km * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))

    def _format_route_description(self, from_name: str, to_name: str, transportation: str) -> str:
        return f"从{from_name}前往{to_name}，建议使用{transportation}，实际路线请以地图导航为准。"

    def _safe_float(self, value: Any) -> float | None:
        try:
            return float(value)
        except Exception:
            return None


_multi_agent_planner = None


def get_trip_planner_agent() -> MultiAgentTripPlanner:
    """获取多智能体旅行规划系统实例(单例模式)"""
    global _multi_agent_planner

    if _multi_agent_planner is None:
        _multi_agent_planner = MultiAgentTripPlanner()

    return _multi_agent_planner
