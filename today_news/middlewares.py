# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

import os
import re
import time
import redis
import random
import hashlib
from scrapy.http import HtmlResponse
from selenium import webdriver
from scrapy.exceptions import IgnoreRequest
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from selenium.webdriver.chrome.options import Options
from scrapy import signals
from scrapy.utils.python import to_bytes

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


class DupeFiltered(Exception):
    """自定义异常，表示这个 request 是因为去重被过滤的"""
    pass


class RedisDuplicateMiddleware:
    """
    Redis URL去重中间件
    只有当请求的meta中包含detail=True时才会启用去重
    """

    def __init__(self, redis_url, redis_key_expire_time, redis_key_prefix='scrapy:dupefilter:'):
        self.redis_url = redis_url
        self.redis_key_expire_time = redis_key_expire_time
        self.redis_key_prefix = redis_key_prefix
        self.redis_client = None

    @classmethod
    def from_crawler(cls, crawler):
        # 从配置中获取Redis连接信息
        redis_url = crawler.settings.get('REDIS_URL', 'redis://:@localhost:6379/0')
        redis_key_expire_time = crawler.settings.get('REDIS_DUPE_KEY_EXPIRE_TIME', 48 * 60 * 60)
        redis_key_prefix = crawler.settings.get('REDIS_DUPE_KEY_PREFIX', 'scrapy:dupefilter:')

        middleware = cls(redis_url, redis_key_expire_time, redis_key_prefix)

        # 注册spider_opened信号
        crawler.signals.connect(middleware.spider_opened, signal=signals.spider_opened)
        # 注册spider_closed信号
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)

        return middleware

    def spider_opened(self, spider):
        """Spider开启时连接Redis"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            # 测试连接
            self.redis_client.ping()
            spider.logger.info(f"Redis去重中间件已连接: {self.redis_url}")
        except Exception as e:
            spider.logger.error(f"Redis连接失败: {e}")
            self.redis_client = None

    def spider_closed(self, spider):
        """Spider关闭时关闭Redis连接"""
        if self.redis_client:
            self.redis_client.close()

    def process_request(self, request, spider):
        """
        处理请求，检查是否需要去重
        """
        # 检查是否启用去重 (meta中detail==True)
        if not request.meta.get('detail', False):
            return None

        # 如果Redis客户端未初始化，跳过去重检查
        if not self.redis_client:
            spider.logger.warning("Redis客户端未初始化，跳过去重检查")
            return None

        try:
            # 生成URL的指纹（使用SHA1哈希）
            url_fingerprint = self._get_request_fingerprint(request)
            redis_key = f"{self.redis_key_prefix}{spider.name}:{url_fingerprint}"

            # 检查URL是否已存在
            status = self.redis_client.exists(redis_key)
        except Exception as e:
            spider.logger.error(f"Redis去重检查错误: {e}")
            return None

        if status:
            spider.logger.debug(f"URL已采集，跳过: {request.url}")
            raise DupeFiltered("已经采集过的")
        return None

    def process_response(self, request, response, spider):
        """
        处理响应，将成功的请求添加到Redis
        """
        # 检查是否启用去重且请求成功
        if (request.meta.get('detail', False) and
                response.status in [200, 201, 202] and
                self.redis_client):
            try:
                # 生成URL的指纹
                url_fingerprint = self._get_request_fingerprint(request)
                redis_key = f"{self.redis_key_prefix}{spider.name}:{url_fingerprint}"

                # 将URL添加到Redis，设置过期时间（可选）
                expire_time = request.meta.get('redis_expire', self.redis_key_expire_time)  # 默认48小时
                self.redis_client.setex(redis_key, expire_time, '1')
                spider.logger.debug(f"URL已添加到去重集合: {request.url}")

            except Exception as e:
                spider.logger.error(f"Redis添加URL错误: {e}")

        return response

    def _get_request_fingerprint(self, request):
        """
        生成请求的指纹
        可以基于URL、method、body等生成唯一标识
        """
        # 基础指纹：URL + method
        fp = hashlib.sha1()
        fp.update(to_bytes(request.url))
        fp.update(to_bytes(request.method))

        # 如果需要考虑请求体，可以取消下面的注释
        # if request.body:
        #     fp.update(request.body)

        return fp.hexdigest()


# 过滤绝对无用的url
class PreRequestFilterMiddleware:
    """
    URL预请求过滤中间件
    在请求发送到网络之前过滤，完全不发送不需要的请求
    """

    # 定义不需要采集的URL模式
    DENY_PATTERNS = [
        # 娱乐类
        r'/sports?/', r'/musics?/', r'/entertainments?/',
        r'/movies?/', r'/tv/', r'/showbiz/', r'/celebrity/',
        r'/gossip/', r'/game/', r'/gaming/', r'/video-game/',

        # 媒体内容
        r'/video/', r'/audio/', r'/gallery/', r'/photos/',
        r'/slideshow/', r'/picture/', r'/media/',
        r'/podcast/', r'/stream/', r'/playlist/',

        # 商业页面
        r'/shop/', r'/store/', r'/cart/', r'/checkout/',
        r'/product/', r'/buy/', r'/purchase/', r'/price/',
        r'/subscription/', r'/premium/', r'/membership/',
        r'/advertise/', r'/advertisement/', r'/ads/', r'/sponsor/',

        # 其他非新闻
        r'/blog/', r'/event/', r'/calendar/', r'/job/',
        r'/career/', r'/recruitment/', r'/hiring/',
        r'/weather/', r'/horoscope/', r'/lottery/',
        r'/life/', r'/local/', r'/health/', r'/lotteries',
    ]

    def __init__(self, stats):
        self.stats = stats
        # 预编译正则提高性能
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.DENY_PATTERNS
        ]

    @classmethod
    def from_crawler(cls, crawler):
        # 必须有的方法，从crawler创建中间件实例
        return cls(stats=crawler.stats)

    def process_request(self, request, spider):
        """
        在请求发送到下载器之前调用
        如果返回None：继续处理请求
        如果抛出IgnoreRequest：丢弃请求，完全不发送
        """
        # 只过滤非detail页面的url
        if not request.meta.get('detail', False):
            return None

        url = request.url

        # 首先检查URL是否需要过滤
        if self._should_filter(url, spider):
            # 记录统计信息
            self.stats.inc_value('url_filter/filtered_total')

            # 记录到spider日志（可选）
            spider.logger.debug(f'预过滤URL: {url}')

            # 抛出异常，Scrapy会完全丢弃这个请求
            raise IgnoreRequest(f"URL filtered by deny patterns: {url}")

        # 返回None表示继续处理这个请求
        return None

    def _should_filter(self, url, spider):
        """
        判断URL是否应该被过滤
        """
        url_lower = url.lower()

        # 1. 检查是否有爬虫特定的白名单（最高优先级）
        if hasattr(spider, 'CUSTOM_ALLOW_PATTERNS'):
            allow_patterns = spider.CUSTOM_ALLOW_PATTERNS
            for pattern in allow_patterns:
                if pattern in url_lower:
                    return False  # 在白名单中，不过滤

        # 2. 检查是否有爬虫特定的黑名单
        if hasattr(spider, 'CUSTOM_DENY_PATTERNS'):
            deny_patterns = spider.CUSTOM_DENY_PATTERNS
            for pattern in deny_patterns:
                if pattern in url_lower:
                    return True  # 在爬虫特定黑名单中，过滤

        # 3. 应用全局过滤规则
        for pattern in self.compiled_patterns:
            if pattern.search(url):
                return True

        # # 4. 检查文件扩展名
        # if self._is_file_url(url):
        #     return True

        return False

    def _is_file_url(self, url):
        """检查是否是文件下载链接"""
        file_extensions = [
            '.pdf', '.doc', '.docx', '.xls', '.xlsx',
            '.ppt', '.pptx', '.zip', '.rar', '.tar',
            '.gz', '.mp3', '.mp4', '.avi', '.mov',
            '.wmv', '.flv', '.jpg', '.jpeg', '.png',
            '.gif', '.bmp', '.exe', '.dmg', '.iso',
        ]

        url_lower = url.lower()
        for ext in file_extensions:
            if ext in url_lower:
                # 确保是文件扩展名，不是路径的一部分
                if url_lower.endswith(ext) or f'{ext}?' in url_lower or f'{ext}#' in url_lower:
                    return True

        return False


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
            # print(spider.name, '设置了代理', request.url)
            request.meta.update({'proxy': self.proxy_addr})
        # else:
        #     print(spider.name, '不用代理')


class SeleniumSnapshotMiddleware:
    def __init__(self, crawler):
        self.crawler = crawler
        self.driver = None
        self.screenshot_dir = 'snapshots'

        # 创建截图目录
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls(crawler)
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def get_driver(self):
        if not self.driver:
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--window-size=1920,1080')  # 设置窗口大小

            self.driver = webdriver.Chrome(options=chrome_options,
                                           executable_path=r'C:\Users\admin\Python39\chromedriver83.exe')
        return self.driver

    def process_request(self, request, spider):
        # 检查是否需要使用Selenium处理并保存快照
        if request.meta.get('snapshot'):
            driver = self.get_driver()

            try:
                # 访问页面
                driver.get(request.url)

                # 等待页面加载
                wait_time = request.meta.get('selenium_wait', 3)
                time.sleep(wait_time)

                # 执行滚动操作确保内容加载
                self.scroll_page(driver)

                # 保存截图
                screenshot_path = self.save_screenshot(driver, request.url, spider.name)

                # 获取页面源码
                page_source = driver.page_source

                # 返回Response对象
                # raise Exception('bad')
                return HtmlResponse(
                    url=driver.current_url,
                    body=page_source.encode('utf-8'),
                    encoding='utf-8',
                    request=request,
                )

            except Exception as e:
                spider.logger.error(f"Selenium处理失败: {request.url}, 错误: {str(e)}")
                # 抛出异常，这将触发该请求的errback回调链
                raise IgnoreRequest(f"Selenium processing failed: {str(e)}") from e

        return None

    def scroll_page(self, driver):
        """滚动页面确保所有内容加载"""
        # 滚动到页面底部
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        # 滚动回顶部
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.5)

    def save_screenshot(self, driver, url, spider_name):
        """保存截图并返回文件路径"""
        # 生成文件名
        from urllib.parse import urlparse
        import hashlib

        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace('.', '_')
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]

        filename = f"{spider_name}_{domain}_{url_hash}.png"
        filepath = os.path.join(self.screenshot_dir, filename)

        total_width = driver.execute_script("return document.body.scrollWidth")
        total_height = driver.execute_script("return document.body.scrollHeight")

        # 设置窗口大小为完整页面尺寸
        driver.set_window_size(total_width, total_height)

        # 保存截图
        driver.save_screenshot(filepath)
        return filepath

    def spider_closed(self, spider):
        if self.driver:
            self.driver.quit()
            self.driver = None


class SeleniumMiddleware:
    def __init__(self):
        chrome_options = Options()
        # chrome_options.add_argument('--headless')  # 无头模式
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        self.driver = webdriver.Chrome(options=chrome_options, executable_path=r'C:\Users\admin\Python39\chromedriver83.exe')

    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls()
        crawler.signals.connect(middleware.spider_closed, signal=signals.spider_closed)
        return middleware

    def process_request(self, request, spider):
        # 检查是否需要使用Selenium处理
        if request.meta.get('snapshot'):
            self.driver.get(request.url)

            # 可选：等待页面加载完成
            time.sleep(2)

            # 获取页面源码
            page_source = self.driver.page_source

            return HtmlResponse(
                url=request.url,
                body=page_source,
                encoding='utf-8',
                request=request
            )
        return None

    def spider_closed(self):
        self.driver.quit()