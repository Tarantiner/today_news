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


class MainichiSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "每日新闻"
    allowed_domains = ["mainichi.jp"]
    start_urls = [
        # "https://mainichi.jp/seiji/",  # 政治
        # "https://mainichi.jp/biz/",  # 经济
        "https://mainichi.jp/world/",  # 国际
    ]

    async def start(self):
        for base_url in self.start_urls:
            page = 1

            # 先请求第一页，用于判断是否继续
            first_url = f'{base_url}'
            yield scrapy.Request(
                first_url,
                callback=self.parse_with_continuation,
                meta={
                    'base_url': base_url,
                    'current_page': page,
                    'is_first': True
                }
            )

    def parse_detail(self, response):
        itm = response.meta['item']
        if response.xpath('//div[@class="paywallpanel-wrapper"]'):
            self.logger.info(f'内容为付费：{response.url}')
            return
        try:
            pub_time = self.to_utc_string(response.xpath('//meta[@name="firstcreate"]/@content').extract_first(''))
        except:
            self.logger.info(f'提取发布时间失败：{response.url}')
            return
        if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get(
                'NEWS_EXPIRE_DAYS')):
            self.logger.info(f'新闻过期：{pub_time}|{response.url}')
            return
        itm['pub_time'] = pub_time

        d1 = response.xpath('//section[@id="articledetail-body"]')
        clean_text = d1.xpath('./p | ./h1 | ./h2 | ./h3 | ./h4').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p:
                txt_list.append(_p)
        # print('\n'.join(txt_list))
        itm['content'] = '\n'.join(txt_list)
        if not itm['content']:
            itm['content'] = 'content'

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        if not itm.get('keywords'):
            itm['keywords'] = response.xpath('//meta[@name="keywords"]/@content').extract_first('')

        try:
            itm['source'] = re.search('"publisher".*?"name": ?"(.*?)"', response.text, re.S).group(1)
        except:
            itm['source'] = ''

        try:
            itm['mod_time'] = self.to_utc_string(response.xpath('//meta[@name="lastupdate"]/@content').extract_first(''))
        except:
            itm['mod_time'] = ''

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse_with_continuation(self, response):
        base_url = response.meta['base_url']
        current_page = response.meta['current_page']
        is_first = response.meta.get('is_first', False)
        response.selector.remove_namespaces()
        should_continue = True

        for itm in response.xpath('//ul[contains(@class, "articlelist")]/li'):
            url = itm.xpath('./a/@href').extract_first('')
            if not url:
                continue
            if not url.startswith('//'):
                continue
            url = f'https:{url}'
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = self.clean_phrase(
                itm.xpath('./a//node()[contains(@class,"articlelist-title")]/text()').extract_first(''))
            if not title:
                continue
            pub_time = self.to_utc_string(itm.xpath('./a//span[contains(@class, "articletag-date")]/text()').extract_first(''))
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get(
                    'NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                if should_continue:
                    should_continue = False
                continue

            mod_time = ''
            desc = ''
            lang = ''
            content = ''
            source = ''
            keywords = ''

            img_list = itm.xpath('./a//div[contains(@class, "articlelist-image")]/picture//img')
            if img_list:
                img_url = img_list[0].xpath('./@src').extract_first('')
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

        # if should_continue:
        #     next_page = current_page + 1
        #     next_url = f'{base_url}{next_page}?_={int(time.time() * 1000)}'
        #     print('继续访问', next_url)
        #     yield scrapy.Request(
        #         next_url,
        #         callback=self.parse_with_continuation,
        #         meta={
        #             'base_url': base_url,
        #             'current_page': next_page,
        #             'is_first': False
        #         }
        #     )
        # else:
        #     print('应当停止', response.url)
