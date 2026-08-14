import re
import json
import scrapy
import random
import datetime
import traceback
from urllib import parse
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class CteeSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "工商时报"
    start_urls = ["https://www.ctee.com.tw/sitemaps/sitemap_newstoday.xml"]

    IMPERSONATE_LIST = [
        # "chrome110",
        "chrome120",
    ]

    async def start(self):
        for url in self.start_urls:
            impersonate = random.choice(self.IMPERSONATE_LIST)
            yield scrapy.Request(url, meta={
                'use_curl_cffi': True,
                'curl_cffi_impersonate': impersonate,
                'headers': {
                    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
                }
            })


    def parse_detail(self, response):
        itm = response.meta['item']
        mod_time = response.xpath('//meta[@property="article:modified_time"]/@content').extract_first('')
        if mod_time:
            itm['mod_time'] = self.to_utc_string(self.name,mod_time)

        d1 = response.xpath('//div[@class="content__body"]//article')
        clean_text = d1.xpath('.//h1 | .//h2 | .//p').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p:
                # print([_p])
                txt_list.append(_p)
        # print('\n'.join(txt_list))
        itm['content'] = '\n'.join(txt_list)
        if not itm['content']:
            itm['content'] = 'content'

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        if not itm.get('images'):
            img_list = response.xpath('//figure//img')
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
            itm['images'] = images

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
        if response.request.url == self.start_urls[0]:
            response.selector.remove_namespaces()
            for itm in response.xpath('//url'):
                url = itm.xpath('./loc/text()').extract_first('')
                if not url:
                    continue
                if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                    continue
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
                try:
                    source = re.search(r'<news:name>(.*?)</news:name>', s).group(1)
                except:
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
                yield scrapy.Request(url, meta={'snapshot': True, 'item': itm, 'detail': True},
                                     callback=self.parse_detail, errback=self.parse_detail_failed)
