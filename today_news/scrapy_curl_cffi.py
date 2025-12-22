# scrapy_curl_cffi.py
import scrapy
from curl_cffi import requests
from scrapy.core.downloader.handlers.http import HTTPDownloadHandler
from scrapy.http import Headers, TextResponse
from twisted.internet.defer import Deferred
from twisted.internet import reactor
import logging

class CurlCffiDownloadHandler(HTTPDownloadHandler):
    def __init__(self, settings, crawler=None):
        super().__init__(settings, crawler)
        self.impersonate = settings.get("CURL_CFFI_IMPERSONATE", "chrome124")  # 或 chrome120, edge101 等
        self.verify = settings.getbool("CURL_CFFI_VERIFY", True)
        self.timeout = settings.getint("CURL_CFFI_TIMEOUT", 30)

    def download_request(self, request, spider):
        if not request.meta.get('use_curl_cffi', False):
            # 没打标记的走原生 Scrapy
            return super().download_request(request, spider)

        # 用 curl_cffi 发起请求
        d = Deferred()

        def _request():
            try:
                # 支持所有 scrapy Request 的参数
                headers = request.headers.to_unicode_dict() if request.headers else {}
                proxy = request.meta.get('proxy')

                # headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}

                # curl_cffi 的核心：完美模拟 Chrome 的 TLS + HTTP/2 指纹
                resp = requests.request(
                    method=request.method,
                    url=request.url,
                    headers=headers,
                    data=request.body,
                    params=request.meta.get('params'),  # GET 参数
                    json=request.meta.get('json'),
                    cookies=request.cookies,
                    impersonate=request.meta.get('curl_cffi_impersonate') or self.impersonate,        # ← 关键！指纹模拟
                    verify=self.verify,
                    timeout=self.timeout,
                    proxies={'http': proxy, 'https': proxy} if proxy else None,
                    allow_redirects=False,  # Scrapy 自己处理重定向
                )

                # 构造 Scrapy 的 Response 对象
                # print(resp.status_code)
                resp_headers = Headers(resp.headers)
                if 'Content-Encoding' in resp_headers:
                    del resp_headers['Content-Encoding']  # 关键！
                if 'content-encoding' in resp_headers:
                    del resp_headers['content-encoding']

                # 同时可以顺手删掉 Transfer-Encoding、Vary 等干扰头（可选）
                for header in ['Transfer-Encoding', 'Vary', 'Content-Length']:
                    resp_headers.pop(header, None)
                resp_cookies = resp.cookies

                # scrapy_resp = request.meta.get('response_class', scrapy.http.Response)(
                #     url=resp.url,
                #     status=resp.status_code,
                #     headers=resp_headers,
                #     body=resp.content,
                #     request=request,
                #     # cookies=resp_cookies,
                #     flags=['curl_cffi'],
                # )

                scrapy_resp = TextResponse(
                    url=resp.url,
                    status=resp.status_code,
                    headers=resp_headers,
                    body=resp.content,  # 已经是解压后的明文
                    request=request,
                    flags=['curl_cffi'],  # 会在日志后面附加说明
                    encoding='utf-8',  # 必须指定！否则 selector 可能乱码
                )

                d.callback(scrapy_resp)
            except Exception as e:
                d.errback(e)

        reactor.callInThread(_request)
        return d


