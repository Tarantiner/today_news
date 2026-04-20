import sys
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

from scrapy.utils.log import configure_logging
from scrapy.crawler import CrawlerRunner
from scrapy.utils.project import get_project_settings
from scrapy.settings import Settings

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import epollreactor


# =========================
# 1. Linux reactor（必须最先执行）
# =========================
#epollreactor.install()


# =========================
# 2. log配置
# =========================
log_dir = './logs'
os.makedirs(log_dir, exist_ok=True)

configure_logging(install_root_handler=True)


def setup_spider_file_logging(name):
    formatter = logging.Formatter(
        '%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(log_dir, f'{name}.log'),
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )

    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    return file_handler


file_handler = setup_spider_file_logging('crawler')
logging.getLogger('scrapy').addHandler(file_handler)


# =========================
# 3. settings
# =========================
settings = get_project_settings()

# ❌ 删除 selectreactor（Linux 不要用）
# settings.set('TWISTED_REACTOR', 'twisted.internet.selectreactor.SelectReactor')
settings.set(
    'TWISTED_REACTOR',
    'twisted.internet.asyncioreactor.AsyncioSelectorReactor'
)
# ✔️ Linux 推荐（Scrapy新版本更推荐这个）
settings.set('TWISTED_REACTOR', 'twisted.internet.epollreactor.EPollReactor')


priority_spider_list = sorted(
    [
        (name,
         cfg.get('priority') or 0,
         cfg.get('custom_settings') or {})
        for name, cfg in (settings.get('SPIDER_SETTINGS') or {}).items()
        if cfg.get('enabled')
    ],
    key=lambda x: x[1],
    reverse=True
)

print(priority_spider_list)


# =========================
# 4. crawl
# =========================
@defer.inlineCallbacks
def crawl():
    deferred_list = []

    for spider_name, _, custom_settings in priority_spider_list:

        final_settings = Settings(settings.copy())
        final_settings.update(custom_settings)

        runner = CrawlerRunner(final_settings)

        print(f'启动了 {spider_name}')

        deferred = runner.crawl(spider_name)
        deferred_list.append(deferred)

    yield defer.DeferredList(deferred_list)

    reactor.stop()


# =========================
# 5. run
# =========================
crawl()
reactor.run()
