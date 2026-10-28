import os
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
from cloud_app import app


class MapProxyTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.env_patch = patch.dict(os.environ, {
            'AMAP_WEB_JS_KEY': 'browser-key',
            'AMAP_WEB_JS_SECURITY_CODE': 'server-secret',
        })
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.connection_patch = patch('app.api.routes.map_proxy.http.client.HTTPSConnection')
        self.connection_factory = self.connection_patch.start()
        self.addCleanup(self.connection_patch.stop)
        self.connection = self.connection_factory.return_value
        self.upstream = self.connection.getresponse.return_value
        self.upstream.status = 200
        self.upstream.read.return_value = b'{"status":"1"}'
        self.upstream.getheader.return_value = 'application/json'

    def test_web_service_proxy_replaces_client_credentials(self):
        response = self.client.get('/_AMapService/v3/place/text?keywords=park&key=wrong&jscode=wrong',
                                   headers={'Referer': 'https://example.com/result'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.connection_factory.call_args.args[0], 'restapi.amap.com')
        args = self.connection.request.call_args
        query = parse_qs(urlsplit(args.args[1]).query)
        self.assertEqual(query, {'keywords': ['park'], 'key': ['browser-key'], 'jscode': ['server-secret']})
        self.assertEqual(args.kwargs['headers']['referer'], 'https://example.com/result')
        self.connection.close.assert_called_once()

    def test_custom_style_proxy_uses_webapi_host(self):
        response = self.client.get('/_AMapService/v4/map/styles')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.connection_factory.call_args.args[0], 'webapi.amap.com')

    def test_missing_security_code_returns_clear_failure_without_query(self):
        with patch.dict(os.environ, {'AMAP_WEB_JS_SECURITY_CODE': ''}):
            response = self.client.get('/_AMapService/v3/place/text')
            config = self.client.get('/api/client-config').json()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(config['amap_service_host'], '')
        self.connection_factory.assert_not_called()

    def test_invalid_path_cannot_select_arbitrary_host(self):
        for path in ('https://example.com', 'v3/a.b', 'v3//example'):
            response = self.client.get('/_AMapService/' + path)
            self.assertEqual(response.status_code, 404)
        self.connection_factory.assert_not_called()

    def test_upstream_redirect_does_not_expose_credential_url(self):
        self.upstream.status = 302
        response = self.client.get('/_AMapService/v3/place/text')
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('location', response.headers)
        self.assertNotIn('server-secret', response.text)

    def test_network_error_does_not_expose_secret(self):
        self.connection.request.side_effect = OSError('failure at ?jscode=server-secret')
        response = self.client.get('/_AMapService/v3/place/text')
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('server-secret', response.text)
        self.connection.close.assert_called_once()

    def test_reflected_security_code_is_redacted(self):
        self.upstream.read.return_value = b'{"error":"server-secret"}'
        response = self.client.get('/_AMapService/v3/place/text')
        self.assertNotIn('server-secret', response.text)


if __name__ == '__main__':
    unittest.main()
