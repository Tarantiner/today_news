import scrapy
import datetime
from today_news.items import TodayNewsItem


class ApnewsSpider(scrapy.Spider):
    name = "美联社"
    allowed_domains = ["apnews.com"]
    start_urls = ["https://apnews.com/news-sitemap-content.xml"]

    # 统一utc时间字符串
    def parse_time(self, time_str):
        try:
            if not time_str:
                return '1970-01-01 00:00:00'
            # 直接解析带时区的时间
            dt = datetime.datetime.fromisoformat(time_str)  # Python 3.7+
            print(dt)  # 2025-11-09 16:46:27-05:00

            # 格式化为字符串
            formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
            # print(formatted)  # 2025-11-09 16:46:27

            # 转换为本地时间
            local_dt = dt.astimezone()
            # print(local_dt.strftime("%Y-%m-%d %H:%M:%S %Z"))  # 2025-11-10 05:46:27 CST

            # 转换为UTC时间
            utc_dt = dt.astimezone(datetime.timezone.utc)
            format_time = utc_dt.strftime("%Y-%m-%d %H:%M:%S")  # 2025-11-09 21:46:27 UTC
            print(f'{time_str}==>{format_time}')
            return format_time
        except Exception as e:
            self.logger.info(f'转换时间失败:{type(e)}|{time_str}')
            return ''

    def parse(self, response):
        if response.request.url == self.start_urls[0]:
            response.selector.remove_namespaces()
            for itm in response.xpath('//url'):
                url = itm.xpath('./loc/text()').extract_first('')
                pub_time = self.parse_time(itm.xpath('./news/publication_date/text()').extract_first(''))
                mod_time = self.parse_time(itm.xpath('./lastmod/text()').extract_first(''))
                title = itm.xpath('./news/title/text()').extract_first('')
                desc = ''
                lang = itm.xpath('./news/publication/language/text()').extract_first('')
                content = 'content'
                source = itm.xpath('./news/publication/name/text()').extract_first('')
                keywords = ''
                images = []

                itm = TodayNewsItem(
                    url=url,
                    pub_time=pub_time,
                    mod_time=mod_time,
                    title=title,
                    desc=desc,
                    lang=lang,
                    content=content,
                    source=source,
                    keywords=keywords,
                    name=self.name,
                    images=images,
                )
                yield itm



# from scrapy.spiders import SitemapSpider
# class NewsSitemapSpider(SitemapSpider):
#     name = 'apnews'
#
#     # 指定sitemap URL
#     sitemap_urls = [
#         'https://apnews.com/news-sitemap-content.xml',
#     ]
#
#     # # 可选：从robots.txt自动发现sitemap
#     # sitemap_follow = ['sitemap-news']  # 只跟踪新闻sitemap
#     sitemap_rules = [
#         # 匹配规则：(正则表达式, 回调函数)
#         ('.', 'parse_news_from_sitemap'),
#     ]
#
#     def parse_news_from_sitemap(self, response):
#         print('debug')
