import sys
from twisted.internet import reactor, defer
from scrapy.utils.log import configure_logging
from scrapy.crawler import CrawlerRunner
from scrapy.utils.project import get_project_settings
import warnings
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

# warnings.filterwarnings('ignore')  # 禁用所有警告

# 确保日志目录存在
log_dir = './logs'
os.makedirs(log_dir, exist_ok=True)

# 配置基础控制台日志
configure_logging(install_root_handler=True)


def setup_spider_file_logging(name):
    """为每个爬虫设置按日期切割的文件日志"""
    # 创建spider特定的日志格式
    formatter = logging.Formatter(
        '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 创建按日期切割的文件处理器
    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, f'{name}.log'),
        when='midnight',  # 每天午夜切割
        interval=1,  # 每天
        backupCount=7,  # 保留7天
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)  # 文件记录所有DEBUG及以上日志

    return file_handler


# 设置该爬虫的文件日志
file_handler = setup_spider_file_logging('crawler')
logging.getLogger('scrapy').addHandler(file_handler)


# 获取项目设置
settings = get_project_settings()
settings.set('TWISTED_REACTOR', 'twisted.internet.selectreactor.SelectReactor')
priority_spider_list = sorted(
    [(spider_name, spider_config.get('priority') or 0, spider_config.get('custom_settings') or {}) for
     spider_name, spider_config in (settings.get('SPIDER_SETTINGS') or {}).items() if spider_config.get('enabled')],
    key=lambda x: x[1], reverse=True)


@defer.inlineCallbacks
def crawl():
    deferred_list = []

    for spider_itm in priority_spider_list:
        spider_name = spider_itm[0]
        custom_settings = spider_itm[2]

        # 为每个爬虫创建独立的设置
        from scrapy.settings import Settings
        final_settings = Settings(settings.copy())
        final_settings.update(custom_settings)

        # 为每个爬虫创建独立的 runner
        runner = CrawlerRunner(final_settings)

        print(f'启动了 {spider_name}')

        # 立即启动爬虫，不等待完成
        deferred = runner.crawl(spider_name)
        deferred_list.append(deferred)

    # 等待所有爬虫完成
    yield defer.DeferredList(deferred_list)
    reactor.stop()


crawl()
reactor.run()
