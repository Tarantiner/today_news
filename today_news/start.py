import sys
from twisted.internet import reactor, defer
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
import warnings
# warnings.filterwarnings('ignore')  # 禁用所有警告

# 获取项目设置
settings = get_project_settings()

# settings.set('TWISTED_REACTOR', 'twisted.internet.asyncioreactor.AsyncioSelectorReactor')
settings.set('TWISTED_REACTOR', 'twisted.internet.selectreactor.SelectReactor')

# 创建进程
process = CrawlerProcess(settings)

# 动态获取所有 spider 名称（或手动指定列表）
for spider_name in process.spider_loader.list():  # 自动列出所有 spider
    if spider_name != 'NOWnews今日新聞':
        continue
    process.crawl(spider_name)  # 可添加参数，如 process.crawl(spider_name, arg1='value')
    print('启动了', spider_name)

# 启动进程（阻塞直到所有 spider 完成）
process.start()  # 或使用 CrawlerRunner + defer.DeferredList 异步处理

"""
2025-11-14 10:46:02 [scrapy.statscollectors] INFO: Dumping Scrapy stats:
{'downloader/request_bytes': 845,
 'downloader/request_count': 2,
 'downloader/request_method_count/GET': 2,
 'downloader/response_bytes': 128580,
 'downloader/response_count': 2,
 'downloader/response_status_count/200': 2,
 'elapsed_time_seconds': 11.816113,
 'finish_reason': 'finished',
 'finish_time': datetime.datetime(2025, 11, 14, 2, 46, 2, 606366, tzinfo=datetime.timezone.utc),
 'httpcompression/response_bytes': 767435,
 'httpcompression/response_count': 2,
 'item_scraped_count': 1525,
 'items_per_minute': 8318.181818181818,
 'log_count/DEBUG': 4651,
 'log_count/INFO': 59,
 'log_count/WARNING': 88,
 'response_received_count': 2,
 'responses_per_minute': 10.90909090909091,
 'robotstxt/request_count': 1,
 'robotstxt/response_count': 1,
 'robotstxt/response_status_count/200': 1,
 'scheduler/dequeued': 1,
 'scheduler/dequeued/memory': 1,
 'scheduler/enqueued': 1,
 'scheduler/enqueued/memory': 1,
 'start_time': datetime.datetime(2025, 11, 14, 2, 45, 50, 790253, tzinfo=datetime.timezone.utc)}
"""