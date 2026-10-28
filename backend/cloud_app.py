"""Production entry point: serve the Vue build and selected application APIs."""
from pathlib import Path
import os
from fastapi import HTTPException
from fastapi.responses import FileResponse
from app.api.main import app
from app.api.routes.map_proxy import router as map_proxy_router

app.include_router(map_proxy_router)

WEB = Path(os.getenv('FRONTEND_DIST', '/app/frontend/dist')).resolve()

@app.get('/api/client-config')
def client_config():
    # Only a domain-restricted browser key belongs here, never AMAP_API_KEY or LLM_API_KEY.
    return {
        'amap_web_js_key': os.getenv('AMAP_WEB_JS_KEY', '').strip(),
        'amap_service_host': '/_AMapService'
        if os.getenv('AMAP_WEB_JS_SECURITY_CODE', '').strip() else '',
    }

@app.get('/result', include_in_schema=False)
def result_page():
    if not (WEB/'index.html').is_file():
        raise HTTPException(status_code=404)
    return FileResponse(WEB/'index.html')

@app.get('/assets/{name:path}', include_in_schema=False)
def assets(name: str):
    path=(WEB/'assets'/name).resolve()
    if not path.is_relative_to(WEB/'assets') or not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path)

# Replace the API information page only in the production entry point.
app.router.routes[:] = [route for route in app.router.routes
                       if not (getattr(route,'path',None)=='/' and 'GET' in getattr(route,'methods',set()))]

@app.get('/', include_in_schema=False)
def home():
    if not (WEB/'index.html').is_file():
        raise HTTPException(status_code=503, detail='Frontend build is not available.')
    return FileResponse(WEB/'index.html')
