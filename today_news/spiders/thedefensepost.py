import re
import json
import scrapy
import datetime
import traceback
from urllib import parse
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class TheDefensePostSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "防务邮报"
    last_days = set()
    allowed_domains = ["thedefensepost.com"]
    start_urls = [
        "https://thedefensepost.com/latest/",
    ]

    # 统一utc时间字符串
    def parse_time(self, time_str):
        try:
            if not time_str:
                return ''
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

    def parse_detail(self, response):
        try:
            data = json.loads(response.xpath('//script[@id="tie-schema-json"]/text()').extract_first())
            title = data.get('name') or ''
            if not title:
                return
            pub_time = self.parse_time(data.get('datePublished') or '')
            if not pub_time:
                return
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{response.url}')
                return
            content = data.get('articleBody').strip('\n ').replace('\n\n\n\n', '\n')
            if not content:
                return
            mod_time = self.parse_time(data.get('dateModified') or '')
            desc = data.get('description') or ''
            keywords = data.get('keywords') or ''
            publisher = (data.get('publisher') or {}).get('name') or ''
            is_origin = True if publisher == 'The Defense Post' else False
            img_url = (data.get('image') or {}).get('url') or ''

            itm = TodayNewsItem(
                url=response.url,
                pub_time=pub_time,
                mod_time=mod_time,
                title=title,
                desc=desc,
                lang='',
                content=content,
                source=publisher,
                keywords=keywords,
                name=self.name,
                images=[{'url': img_url, 'caption': '', 'img_time': ''}] if img_url.startswith('http') else [],
            )
            yield itm
        except:
            self.logger.warning(f'提取{response.url}内容失败|{traceback.format_exc()}')
            return

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        lis = response.xpath('//ul[@id="posts-container"]/li')
        for itm in lis:
            _t = itm.xpath('./div[@class="day-month"]/span/text()').extract_first('')
            if not _t:
                continue
            self.last_days.add(_t)
            if len(self.last_days) >= 3:
                self.logger.info(f'已处理到{_t}，停止抓取')
                break
            url = itm.xpath('.//h2[@class="post-title"]/a/@href').extract_first('')
            if url and url.startswith('http'):
                yield scrapy.Request(url, meta={'snapshot': True, 'detail': True},
                                     callback=self.parse_detail, errback=self.parse_detail_failed)
        page = response.request.meta.get('page') or 1
        if len(self.last_days) < 3:
            page += 1
            yield scrapy.Request(f'https://thedefensepost.com/latest/page/{page}/', meta={'page': page},
                                 callback=self.parse)


        # if response.request.url == self.start_urls[0]:
        #     response.selector.remove_namespaces()
        #     for itm in response.xpath('//url'):
        #         url = itm.xpath('./loc/text()').extract_first('')
        #         if not url:
        #             continue
        #         if self.match_invalid_url(url):
        #             continue
        #         title = itm.xpath('./news/title/text()').extract_first('')
        #         if not title:
        #             continue
        #         pub_time = self.parse_time(itm.xpath('./news/publication_date/text()').extract_first(''))
        #         if not pub_time:
        #             continue
        #         # 检查过期资讯并过滤
        #         if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
        #             self.logger.info(f'新闻过期：{pub_time}|{url}')
        #             continue
        #
        #         mod_time = self.parse_time(itm.xpath('./lastmod/text()').extract_first(''))
        #         desc = ''
        #         lang = itm.xpath('./news/publication/language/text()' ).extract_first('')
        #         content = ''
        #         source = itm.xpath('./news/publication/name/text()').extract_first('')
        #         keywords = ''
        #         images = []
        #
        #         itm = TodayNewsItem(
        #             url=url,
        #             pub_time=pub_time,
        #             mod_time=mod_time,
        #             title=title,
        #             desc=desc,
        #             lang=lang,
        #             content=content,
        #             source=source,
        #             keywords=keywords,
        #             name=self.name,
        #             images=images,
        #         )
        #         # yield itm
        #         yield scrapy.Request(url, meta={'snapshot': True, 'item': itm, 'detail': True},
        #                              callback=self.parse_detail, errback=self.parse_detail_failed)
