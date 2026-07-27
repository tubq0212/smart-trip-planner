# 智能旅行规划助手

一个面向自由行场景的旅行规划工具。用户输入目的地、出行日期、旅行天数、交通方式、住宿偏好和旅行兴趣后，系统会生成包含景点、路线、酒店、餐饮、天气、预算和地图展示的旅行计划。

项目采用前后端分离架构，支持两种运行模式：

- 快速模式：不调用 LLM，优先使用高德 Web API 和内置真实 POI 数据生成稳定行程，方便本地调试。
- LLM 模式：启用 HelloAgents 多智能体流程，结合大模型和地图工具完成行程规划。

## 功能特性

- 旅行需求表单：支持目的地、日期、天数、交通方式、住宿偏好和兴趣标签输入。
- 智能行程生成：按天生成景点、餐饮、住宿、天气和预算信息。
- 真实 POI 推荐：支持真实景点、酒店和餐饮推荐，高德 API 不可用时使用内置真实城市数据兜底。
- 路线规划展示：根据景点经纬度估算相邻景点距离和通勤时间。
- 地图交互联动：景点卡片和地图 Marker 双向联动，支持信息窗、视野适配和路线连线。
- 行程编辑：支持景点上移、下移、删除，编辑后自动刷新路线和地图。
- 快速测试模式：关闭 LLM 时仍可生成行程，便于本地调试和功能验证。
- 结果导出：支持将旅行计划导出为图片或 PDF。
- 自动化验证：后端提供 pytest 测试，前端支持 TypeScript 构建检查。

## 技术栈

前端：

- Vue 3
- TypeScript
- Vite
- Ant Design Vue
- Axios
- 高德地图 Web JS API
- html2canvas
- jsPDF

后端：

- Python
- FastAPI
- Uvicorn
- Pydantic
- Pydantic Settings
- HelloAgents
- MCPTool
- 高德 Web 服务 API
- pytest

## 项目结构

```text
smart-trip-planner/
├─ backend/
│  ├─ app/
│  │  ├─ agents/
│  │  │  └─ trip_planner_agent.py
│  │  ├─ api/
│  │  │  ├─ main.py
│  │  │  └─ routes/
│  │  │     ├─ map.py
│  │  │     ├─ poi.py
│  │  │     └─ trip.py
│  │  ├─ models/
│  │  │  └─ schemas.py
│  │  ├─ services/
│  │  │  ├─ amap_service.py
│  │  │  ├─ llm_service.py
│  │  │  └─ unsplash_service.py
│  │  └─ config.py
│  ├─ tests/
│  │  └─ test_trip_fast_mode.py
│  ├─ requirements.txt
│  ├─ requirements-dev.txt
│  └─ run.py
├─ frontend/
│  ├─ src/
│  │  ├─ services/
│  │  │  └─ api.ts
│  │  ├─ types/
│  │  │  └─ index.ts
│  │  ├─ views/
│  │  │  ├─ Home.vue
│  │  │  └─ Result.vue
│  │  ├─ App.vue
│  │  └─ main.ts
│  ├─ package.json
│  └─ vite.config.ts
├─ README.md
└─ .gitignore
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/tubq0212/smart-trip-planner.git
cd smart-trip-planner
```

### 2. 配置后端环境

```bash
cd backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env
```

编辑 `backend/.env`：

```env
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
LOG_LEVEL=INFO

# true 表示不调用 LLM，适合本地调试和演示
TRIP_FAST_MODE=true

# 高德 Web 服务 API Key
AMAP_API_KEY=your_amap_api_key_here

# 如需启用 LLM 模式，再配置以下内容
LLM_MODEL_ID=your-model-name
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=your-api-base-url
LLM_TIMEOUT=120
```

启动后端：

```bash
.venv\Scripts\python.exe run.py
```

后端地址：

```text
http://localhost:8000
```

API 文档：

```text
http://localhost:8000/docs
```

### 3. 配置前端环境

另开一个终端：

```bash
cd frontend
npm install
copy .env.example .env
```

编辑 `frontend/.env`：

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_AMAP_WEB_KEY=your_amap_web_api_key_here
VITE_AMAP_WEB_JS_KEY=your_amap_web_js_key_here
```

启动前端：

```bash
npm run dev
```

访问：

```text
http://localhost:5173
```

## 运行测试

后端测试：

```bash
cd backend
.venv\Scripts\python.exe -m pytest -q
```

前端构建检查：

```bash
cd frontend
npm run build
```

当前验证结果：

```text
backend: 3 passed
frontend: build success
```

## 核心实现

### 快速模式

`TRIP_FAST_MODE=true` 时，后端不会初始化 LLM，也不会进入完整多智能体链路，而是直接通过快速规划流程生成行程。

实现位置：

```text
backend/app/api/routes/trip.py
backend/app/agents/trip_planner_agent.py
```

主要逻辑：

- 优先通过高德 Web API 获取真实 POI。
- 网络异常或无结果时，使用内置真实城市数据兜底。
- 支持景点、酒店、餐饮、天气、预算和路线段生成。

### 路线段计算

系统会为每天相邻景点生成 `RouteSegment`：

```json
{
  "from_name": "鼓浪屿",
  "to_name": "厦门大学",
  "distance_km": 3.6,
  "duration_minutes": 12,
  "transportation": "公共交通",
  "description": "从鼓浪屿前往厦门大学，建议使用公共交通，实际路线请以地图导航为准。"
}
```

实现方式：

- 使用经纬度和 Haversine 公式估算两点距离。
- 根据交通方式设置不同速度，估算通勤时间。
- 前端编辑景点顺序后，会重新计算路线段并刷新地图连线。

### 地图交互

结果页基于高德地图 Web JS API 实现：

- 景点 Marker 展示。
- 每日路线 Polyline 绘制。
- Marker 信息窗展示。
- 景点卡片点击后定位地图。
- Marker 点击后展开对应日期行程。
- 一键适配全部景点视野。

## API 示例

生成行程：

```http
POST /api/trip/plan
```

请求体：

```json
{
  "city": "厦门",
  "start_date": "2026-07-24",
  "end_date": "2026-07-30",
  "travel_days": 7,
  "transportation": "公共交通",
  "accommodation": "经济型酒店",
  "preferences": ["自然风光", "休闲", "美食"],
  "free_text_input": "希望安排轻松一点"
}
```

返回内容包含：

- `days`：每日行程。
- `attractions`：景点列表。
- `route_segments`：路线段。
- `hotel`：酒店推荐。
- `meals`：餐饮推荐。
- `weather_info`：天气信息。
- `budget`：预算汇总。

## 项目亮点

- 设计快速模式，减少 LLM 超时或外部服务不稳定对本地调试的影响。
- 引入真实 POI 兜底，避免外部接口无结果时出现占位景点数据。
- 将景点、酒店、餐饮、路线、预算统一成结构化响应，前后端类型保持一致。
- 实现地图和行程列表双向联动，提升旅行规划结果的可视化体验。
- 补充 pytest 测试与前端构建检查，保证核心流程可验证。

## 后续规划

- 接入高德真实步行、公交、驾车路线 API，替换当前基于经纬度的估算路线。
- 扩展更多城市的真实景点、酒店、餐饮兜底数据。
- 增加用户收藏、行程保存和历史记录。
- 增加前端交互测试和接口测试覆盖。
- 部署后端服务和前端静态页面，提供在线演示地址。

## License

仅用于学习、作品集展示和技术交流。
