# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

import time
import random
from scrapy.http import HtmlResponse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from scrapy import signals

# useful for handling different item types with a single interface
from itemadapter import ItemAdapter


class TodayNewsSpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, or item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request or item objects.
        pass

    async def process_start(self, start):
        # Called with an async iterator over the spider start() method or the
        # maching method of an earlier spider middleware.
        async for item_or_request in start:
            yield item_or_request

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class TodayNewsDownloaderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class FixedUserAgentMiddleware:
    """随机User-Agent中间件"""

    def __init__(self, user_agents):
        self.user_agents = user_agents

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.get('USER_AGENT'))

    def process_request(self, request, spider):
        request.headers['User-Agent'] = self.user_agents


class RandomUserAgentMiddleware:
    """随机User-Agent中间件"""

    def __init__(self, user_agents):
        self.user_agents = user_agents

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.get('USER_AGENT'))

    def process_request(self, request, spider):
        request.headers['User-Agent'] = random.choice(self.user_agents)


class ProxyMiddleware:
    """代理中间件"""

    def __init__(self, use_proxy, proxy_addr):
        self.use_proxy = use_proxy
        self.proxy_addr = proxy_addr

    @classmethod
    def from_crawler(cls, crawler):
        spider_settings = (crawler.settings.get('SPIDER_SETTINGS') or {}).get(crawler.spider.name) or {}
        proxy_addr = crawler.settings.get('PROXY_ADDR') or ''
        return cls(spider_settings.get('proxy') or False, proxy_addr)

    def process_request(self, request, spider):
        if self.use_proxy and self.proxy_addr:
            print(spider.name, '设置了代理')
            request.meta.update({'proxy': self.proxy_addr})
        else:
            print('不用代理')


# class SeleniumMiddleware:
#     def __init__(self):
#         chrome_options = Options()
#         chrome_options.add_argument('--headless')  # 无头模式
#         chrome_options.add_argument('--no-sandbox')
#         chrome_options.add_argument('--disable-dev-shm-usage')
#
#         self.driver = webdriver.Chrome(options=chrome_options)
#
#     @classmethod
#     def from_crawler(cls, crawler):
#         middleware = cls()
#         crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
#         return middleware
#
#     def process_request(self, request, spider):
#         # 检查是否需要使用Selenium处理
#         if request.meta.get('selenium'):
#             self.driver.get(request.url)
#
#             # 可选：等待页面加载完成
#             time.sleep(2)
#
#             # 获取页面源码
#             page_source = self.driver.page_source
#
#             return HtmlResponse(
#                 url=request.url,
#                 body=page_source,
#                 encoding='utf-8',
#                 request=request
#             )
#         return None
#
#     def spider_closed(self):
#         self.driver.quit()