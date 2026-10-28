"""Same-origin AMap JS proxy; keep the security code on the server."""
import http.client
import os
import re
import ssl
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, Response

router = APIRouter()


@router.get('/_AMapService/{path:path}', include_in_schema=False)
def amap_js_proxy(path: str, request: Request):
    # These are fixed AMap hosts, never a caller-supplied proxy destination.
    if not re.fullmatch(r'v[345]/[A-Za-z0-9_/-]+', path) or '//' in path:
        raise HTTPException(status_code=404)
    key = os.getenv('AMAP_WEB_JS_KEY', '').strip()
    code = os.getenv('AMAP_WEB_JS_SECURITY_CODE', '').strip()
    if not key or not code:
        raise HTTPException(status_code=503, detail='地图配置尚未完成')
    host = 'webapi.amap.com' if path.startswith('v4/map/styles') else 'restapi.amap.com'
    query = [(k, v) for k, v in request.query_params.multi_items()
             if k.lower() not in {'key', 'jscode'}]
    query.extend([('key', key), ('jscode', code)])
    headers = {name: request.headers[name] for name in ('referer', 'origin', 'user-agent')
               if name in request.headers}
    connection = http.client.HTTPSConnection(host, timeout=12, context=ssl.create_default_context())
    try:
        connection.request('GET', '/' + path + '?' + urlencode(query), headers=headers)
        upstream = connection.getresponse()
        # Do not redirect browsers to URLs which could carry server credentials.
        if 300 <= upstream.status < 400:
            raise HTTPException(status_code=502, detail='地图服务暂时不可用')
        body = upstream.read(8 * 1024 * 1024 + 1)
        if len(body) > 8 * 1024 * 1024:
            raise HTTPException(status_code=502, detail='地图响应过大')
        body = body.replace(code.encode(), b'[redacted]')
        return Response(body, status_code=upstream.status, headers={
            'Content-Type': upstream.getheader('Content-Type', 'application/octet-stream'),
            'Cache-Control': 'no-store',
        })
    except (OSError, http.client.HTTPException):
        # Never expose exception URLs, query parameters, or credentials.
        raise HTTPException(status_code=502, detail='地图服务暂时不可用') from None
    finally:
        connection.close()
