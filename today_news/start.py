import sys
from twisted.internet import reactor, defer
from scrapy.settings import Settings
from scrapy.crawler import CrawlerProcess, CrawlerRunner
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
    if spider_name != '美联社':
        continue
    process.crawl(spider_name)  # 可添加参数，如 process.crawl(spider_name, arg1='value')
    print('启动了', spider_name)
# 启动进程（阻塞直到所有 spider 完成）
process.start()  # 或使用 CrawlerRunner + defer.DeferredList 异步处理

# # 按照爬虫配置启动爬虫
# priority_spider_list = sorted([(spider_name, spider_config.get('priority') or 0, spider_config.get('custom_settings') or {}) for spider_name, spider_config in (settings.get('SPIDER_SETTINGS') or {}).items() if spider_config.get('enabled')], key=lambda x: x[1], reverse=True)
# print(f'本程序开启了{len(priority_spider_list)}个爬虫：\n{[i[0] for i in priority_spider_list]}')
# for spider_itm in priority_spider_list:  # 自动列出所有 spider
#     spider_name = spider_itm[0]
#     custom_settings = spider_itm[2]
#     final_settings = Settings(settings.copy())
#     final_settings.update(custom_settings)
#     runner = CrawlerRunner(settings=final_settings)
#     runner.crawl(spider_name)
#     print('启动了', spider_name)
#     runner.join()
#     print('采集完成')

