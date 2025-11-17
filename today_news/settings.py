import os
import json
# Scrapy settings for today_news project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = "today_news"

SPIDER_MODULES = ["today_news.spiders"]
NEWSPIDER_MODULE = "today_news.spiders"

ADDONS = {}


# Crawl responsibly by identifying yourself (and your website) on the user-agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0"

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Concurrency and throttling settings
#CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 1

# Disable cookies (enabled by default)
#COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
#TELNETCONSOLE_ENABLED = False

# Override the default request headers:
#DEFAULT_REQUEST_HEADERS = {
#    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#    "Accept-Language": "en",
#}

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
#SPIDER_MIDDLEWARES = {
#    "today_news.middlewares.TodayNewsSpiderMiddleware": 543,
#}

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#DOWNLOADER_MIDDLEWARES = {
#    "today_news.middlewares.TodayNewsDownloaderMiddleware": 543,
#}


# 每个spider的独立配置，用来配置是否启用代理，是否启用模拟器
try:
    SPIDER_SETTINGS = json.load(open('./spider_settings.json', 'r', encoding='utf-8'))
except:
    SPIDER_SETTINGS = {}


# # 下载图片路径
# IMAGES_STROE = os.path.join(os.path.dirname(__file__), 'images')
# os.makedirs(IMAGES_STROE, exist_ok=True)

# 代理配置
PROXY_ADDR = 'http://127.0.0.1:7890'

# 自定义统计日志
STATS_CLASS = 'today_news.custom_stats.CustomStatsCollector'

# 中间件配置
DOWNLOADER_MIDDLEWARES = {
    # 'today_news.middlewares.RandomUserAgentMiddleware': 400,
    'today_news.middlewares.ProxyMiddleware': 100,
    # 'today_news.middlewares.SeleniumMiddleware': 200,
    'today_news.middlewares.FixedUserAgentMiddleware': 400,
}

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
#EXTENSIONS = {
#    "scrapy.extensions.telnet.TelnetConsole": None,
#}

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
   # "today_news.pipelines.TodayNewsPipeline": 300,
   "today_news.pipelines.DropPipeline": 100,
   "today_news.pipelines.DupePipeline": 200,
   "today_news.pipelines.RobustImagesPipeline": 300,
   "today_news.pipelines.MysqlPipeline": 400,
}

MYSQL_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'chen123',
    'database': 't1',
    'charset': 'utf8mb4'
}

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
#AUTOTHROTTLE_ENABLED = True
# The initial download delay
#AUTOTHROTTLE_START_DELAY = 5
# The maximum download delay to be set in case of high latencies
#AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
#AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
# Enable showing throttling stats for every response received:
#AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
#HTTPCACHE_ENABLED = True
#HTTPCACHE_EXPIRATION_SECS = 0
#HTTPCACHE_DIR = "httpcache"
#HTTPCACHE_IGNORE_HTTP_CODES = []
#HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Set settings whose default value is deprecated to a future-proof value
FEED_EXPORT_ENCODING = "utf-8"
