import os
import re
import json
import scrapy
import random
import datetime
from urllib import parse
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class PoliticoEuSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "欧洲政治新闻"
    # allowed_domains = ["politico.eu"]
    start_urls = [
        "https://www.politico.eu/news-sitemap.xml"
    ]
    IMPERSONATE_LIST = [
        # "chrome110",
        "chrome120",
    ]

    async def start(self):

        for url in self.start_urls:
            impersonate = random.choice(self.IMPERSONATE_LIST)
            yield scrapy.Request(url, meta={
                'use_curl_cffi': True,
                'curl_cffi_impersonate': impersonate
            })

    def parse_detail(self, response):
        cate = response.meta['cate']
        itm = response.meta['item']

        pub_time = self.to_utc_string(self.name, response.xpath('//meta[@property="article:published_time"]/@content').extract_first(''))
        if not pub_time:
            return
        # 检查过期资讯并过滤
        if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get(
                'NEWS_EXPIRE_DAYS')):
            self.logger.info(f'新闻过期：{pub_time}|{response.url}')
            return
        itm['pub_time'] = pub_time
        mod_time = self.to_utc_string(self.name, response.xpath('//meta[@property="article:modified_time"]/@content').extract_first(''))
        if mod_time:
            itm['mod_time'] = mod_time

        d1 = response.xpath('//article[@class="article"]//div[contains(@class, "article__content")]')
        clean_text = d1.xpath('./p').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p:
                print([_p])
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

        if not itm.get('images'):
            img_list = response.xpath('//meta[@property="og:image"]')
            if img_list:
                img_url = img_list[0].xpath('./@content').extract_first('')
                img_caption = ''
                img_time = ''
                images = [
                    {'url': img_url, 'caption': img_caption, 'img_time': img_time}
                ]
                images = images
            else:
                images = []
            itm['images'] = images

        yield itm

    def parse_detail_failed(self, failure):
        return

    def parse(self, response):
        if response.request.url == self.start_urls[0]:
            response.selector.remove_namespaces()
            for itm in response.xpath('//url'):
                url = itm.xpath('./loc/text()').extract_first('')
                if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                    continue
                cate = re.search('https://www.politico.eu/(\S+?)/', url).group(1)  # 'newsletters', 'live-updates', 'news'
                s = itm.extract()
                try:
                    title = re.search(r'<news:title>(.*?)</news:title>', s).group(1)
                    if not title:
                        continue
                    pub_time = re.search(r'<news:publication_date>(.*?)</news:publication_date>', s).group(1)
                    pub_time = self.to_utc_string(self.name, pub_time)
                    if not pub_time:
                        continue
                    # 检查过期资讯并过滤
                    if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                        self.logger.info(f'新闻过期：{pub_time}|{url}')
                        continue
                except:
                    continue

                mod_time = ''
                desc = ''
                try:
                    lang = re.search(r'<news:language>(.*?)</news:language>', s).group(1)
                except:
                    lang = ''
                content = ''
                # source = re.search(r'<news:name>(.*?)</news:name>', s).group(1)
                source = ''
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
                # yield itm
                impersonate = random.choice(self.IMPERSONATE_LIST)
                yield scrapy.Request(url, meta={
                    'snapshot': True, 'item': itm, 'detail': True, 'cate': cate,
                    'use_curl_cffi': True, 'curl_cffi_impersonate': impersonate
                }, callback=self.parse_detail, errback=self.parse_detail_failed)
