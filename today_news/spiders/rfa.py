import re
import json
import scrapy
import datetime
import traceback
from lxml import etree
from urllib import parse
from datetime import datetime, date, timedelta
import calendar
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class RfaSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "自由亚洲电台"

    start_urls = [
        "https://www.rfa.org/arc/outboundfeeds/mandarin/rss/",
        # "https://www.rfa.org/arc/outboundfeeds/english/rss/",
    ]

    def parse_detail(self, response):
        itm = response.meta['item']
        if not itm.get('keywords'):
            itm['keywords'] = response.xpath('//meta[@name="keywords"]/@content').extract_first('')

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        response.selector.remove_namespaces()
        for itm in response.xpath('//channel/item'):
            url = itm.xpath('./link/text()').extract_first('')
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = itm.xpath('./title/text()').extract_first('')
            if not title:
                continue
            mod_time = self.to_utc_string(self.name, itm.xpath('./lastUpdated/text()').extract_first(''))
            pub_time = self.to_utc_string(self.name, itm.xpath('./pubDate/text()').extract_first(''))
            if not pub_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get(
                    'NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                continue

            txt = itm.xpath('./encoded/text()').extract_first('')
            tree = etree.HTML(txt)
            txt_list = []
            for p in tree.xpath('//p'):
                _p = p.text
                if _p:
                    # print([_p])
                    txt_list.append(_p)
            if not txt_list:
                content = 'content'
            else:
                content = '\n'.join(txt_list)

            desc = itm.xpath('./description/text()').extract_first('')
            lang = ''
            source = ''
            keywords = ''

            img_list = itm.xpath('./content')
            if img_list:
                img_url = img_list[0].xpath('./@url').extract_first('')
                img_caption = ''
                img_time = ''
                images = [
                    {'url': img_url, 'caption': img_caption, 'img_time': img_time}
                ]
                images = images
            else:
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
            # yield itm
            yield scrapy.Request(url, meta={'snapshot': True, 'item': itm, 'detail': True},
                                 callback=self.parse_detail, errback=self.parse_detail_failed)


