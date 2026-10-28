# 智能旅行规划助手

输入目的地、日期和出行偏好，生成按天排列的景点、餐饮、住宿与预算。结果页支持调整景点顺序、查看地图标记，以及导出图片或 PDF。

[在线使用](https://smart-trip-planner-mjga.onrender.com/) · [部署配置](docs/CLOUD_DEPLOYMENT.md)

## 运行方式

`TRIP_FAST_MODE=false` 使用 HelloAgents 组织四个 Agent，依次完成景点搜索、天气查询、酒店搜索和行程汇总。前三个 Agent 通过 MCP 调用高德工具，最后一个 Agent 输出行程 JSON，由 Pydantic 校验后返回页面。

`TRIP_FAST_MODE=true` 跳过模型，使用高德 Web 服务查询和内置城市资料生成行程。仓库默认开启此模式，便于未配置模型时运行。模型请求失败或返回内容无法解析时，也会进入备用流程。

前端使用 Vue 3、TypeScript 和 Ant Design Vue；后端使用 FastAPI。地图采用高德 JS API，图片和 PDF 导出使用 html2canvas、jsPDF。

## 本地运行

后端需要 Python 3.12，前端使用 Node.js 22。以下为 Windows 命令。

```powershell
git clone https://github.com/tubq0212/smart-trip-planner.git
cd smart-trip-planner/backend
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
Copy-Item .env.example .env
.venv\Scripts\python.exe run.py
```

另开终端启动前端：

```powershell
cd smart-trip-planner/frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

页面地址为 `http://localhost:5173`，后端接口文档为 `http://localhost:8000/docs`。

启用模型时，在 `backend/.env` 中配置 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_ID` 和 `AMAP_API_KEY`，并设置 `TRIP_FAST_MODE=false`。模型地址填写服务商的基础地址。网页地图另需 JS API Key 和配套安全密钥，详见[部署配置](docs/CLOUD_DEPLOYMENT.md)。

## 代码入口

| 文件 | 用途 |
| --- | --- |
| `backend/app/agents/trip_planner_agent.py` | 四个 Agent、行程解析和备用规划 |
| `backend/app/services/amap_service.py` | MCP 工具发现与注册校验 |
| `backend/app/api/routes/trip.py` | 行程生成接口和模式切换 |
| `backend/app/api/routes/map_proxy.py` | 网页地图安全密钥代理 |
| `backend/cloud_app.py` | 云端接口与前端静态文件入口 |
| `frontend/src/views/Home.vue` | 需求表单 |
| `frontend/src/views/Result.vue` | 行程编辑、地图和导出 |

`POST /api/trip/plan` 接收城市、日期、天数、交通方式、住宿偏好和兴趣标签，返回每日景点、餐饮、酒店、天气和预算。`GET /api/trip/health` 用于检查运行模式和工具注册情况，不会发起模型生成请求。

## 已知限制

- 备用规划中的距离按经纬度估算，地图连线也不是实际导航路线，跨海、换乘等情况需要另行核实。
- 内置资料只覆盖部分城市，价格和预算是估算值；外部查询失败时仍可能返回占位内容。
- 天气查询受高德可用预报范围限制，不能覆盖任意未来日期。
- 多 Agent 依次调用模型，耗时受模型服务和工具响应影响。生成接口在网页端最多等待 6 分钟，SDK 自动重试已关闭。
- `/api/map/*` 中部分独立接口仍待完成结果解析；目前行程页使用的 Agent 工具调用不经过这些封装接口。

## 检查

```powershell
cd backend
.venv\Scripts\python.exe -m pytest tests -q
```

```powershell
cd frontend
npm run build
```

后端测试覆盖运行模式切换、工具注册、地图代理和请求策略，使用模拟模型响应，不需要真实模型密钥。前端构建包含 TypeScript 检查。

## License

仅用于学习、作品集展示和技术交流。
