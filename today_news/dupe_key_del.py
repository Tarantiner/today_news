import redis
from today_news.settings import REDIS_URL
from today_news import abc



def d(x):
    i = 0
    for k in r.keys(f'scrapy:dupefilter:{x}*'):
        s = r.delete(k)
        i += s
    print(f'已删除{i}个')



r = redis.from_url(REDIS_URL)
try:
    d('欧亚时报')  # d('金融时报')  要删的爬虫名
finally:
    r.close()
