import re
import time
import json
import scrapy
import datetime
import traceback
from urllib import parse
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class HrwSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "人权观察网"
    allowed_domains = ["hrw.org"]
    start_urls = [
        "https://www.hrw.org/zh-hans/news"
    ]

    def parse_detail(self, response):
        itm = response.meta['item']
        pub_time = self.to_utc_string(response.xpath('//meta[@property="article:published_time"]/@content').extract_first(''))
        if not pub_time:
            return
        # 检查过期资讯并过滤
        if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get(
                'NEWS_EXPIRE_DAYS')):
            self.logger.info(f'新闻过期：{pub_time}|{response.url}')
            return
        itm['pub_time'] = pub_time
        mod_time = self.to_utc_string(response.xpath('//meta[@property="article:modified_time"]/@content').extract_first(''))
        if mod_time:
            itm['mod_time'] = mod_time

        d1 = response.xpath('//div[contains(@class, "article-body")]')
        clean_text = d1.xpath('./p').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p:
                # print([_p])
                txt_list.append(_p)
        itm = response.meta['item']
        # print('\n'.join(txt_list))
        itm['content'] = '\n'.join(txt_list)
        if not itm['content']:
            itm['content'] = 'content'

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

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
        for itm in response.xpath('//div[@class="views-element-container"]//article'):
            url = itm.xpath('.//div[@class="media-block__content"]/h3/a/@href').extract_first('')
            if not url:
                continue
            if not url.startswith('https'):
                url = parse.urljoin('https://www.hrw.org', url)
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = self.clean_phrase(itm.xpath('.//div[@class="media-block__content"]/h3/a/span/text()').extract_first(''))
            if not title:
                continue
            pub_time = ''
            mod_time = ''
            desc = ''
            lang = ''
            content = ''
            source = ''
            keywords = ''

            img_list = itm.xpath('.//div[contains(@class, "edia-block__image-wrapper")]/img')
            if img_list:
                img_url = img_list[0].xpath('./@src').extract_first('')
                if not img_url.startswith('https'):
                    img_url = parse.urljoin('https://www.hrw.org', img_url)
                img_caption = img_list[0].xpath('./@alt').extract_first('')
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
