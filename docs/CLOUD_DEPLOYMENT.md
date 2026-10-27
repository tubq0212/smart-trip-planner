# Render 云部署

Render 从本仓库根目录 Dockerfile 构建，一个服务同时提供 Vue 页面和 FastAPI 接口，不依赖个人电脑。默认部署快速规划模式，不调用大模型。免费实例可能休眠，网址保留，重新访问时需要等待唤醒。

## 首次部署

1. 使用 GitHub 登录 Render 并完成首次注册。
2. New → Blueprint，选择 tubq0212/smart-trip-planner，读取根目录 render.yaml；或新建 Web Service，选择 Docker、Free 和 main 分支。
3. Dockerfile 使用仓库根目录的 Dockerfile。健康检查路径为 /health。
4. 首次不必填写任何密钥，等待构建和服务启动。
5. 成功后使用 Render 分配的 onrender.com 网址，手机和电脑均可访问。

## 可选配置

- AMAP_API_KEY：高德 Web 服务密钥，只放在 Render 环境变量中，不写入源码或前端。
- AMAP_WEB_JS_KEY：高德浏览器 JS API Key。它会被页面读取，属于客户端配置，需要在高德后台限制实际部署域名；不要填 Web 服务或模型密钥。
- UNSPLASH_ACCESS_KEY：可选照片服务密钥，未配置时使用页面的地点占位图。
- LLM_API_KEY、LLM_BASE_URL、LLM_MODEL_ID：只有计划启用真实模型时才配置，并核对供应商额度及访问控制。默认 TRIP_FAST_MODE=true，不产生模型调用。

这些配置不要提交到 GitHub。Render 免费实例资源有限，模型/MCP 模式还需要单独验证资源和服务可达性，不能仅修改开关就认为已经验证。

## 验证

访问 /health 和 /api/trip/health，确认 fast 模式。生成厦门三日游，验证结果、编辑与导出。地图未配置时会显示提示，行程仍可查看和修改。已内置城市包括厦门、北京、上海、杭州和广州；内置资料和预算是演示数据，出行前应核实。

本地测试入口：backend 中运行 python -m pytest tests。云端入口为 cloud_app:app。Docker 构建不包含 .env、虚拟环境、node_modules 或日志。
