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


class PoliticoComSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "政客网"
    allowed_domains = ["politico.com"]
    start_urls = [
        "https://www.politico.com/news-sitemap-content.xml"
    ]
    IMPERSONATE_LIST = [
        # "chrome110",
        "chrome110",
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
        if cate == 'newsletters':
            d1 = response.xpath('//div[@class="story-text"]')
            clean_text = d1.xpath('./aside/preceding-sibling::p').xpath('string(.)')
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

            if not itm.get('images'):
                img_list = response.xpath('//div[@class="story-text"]//div[@class="story-media"]//figure//picture/img')
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

            yield itm

        elif cate == 'news':
            d1 = response.xpath('//main[@id="main"]')
            clean_text = d1.xpath('.//p[contains(@class, "font-text")]').xpath('string(.)')
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

            if not itm.get('images'):
                img_list = response.xpath('//figure/picture//img')
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

            try:
                mod_time = re.search('"dateModified" ?: ?"(.*?)"', response.text).group(1)
                a, b = mod_time[:len(mod_time)-2], mod_time[-2:]
                mod_time = self.to_utc_string(a + ":"+b)
                if mod_time:
                    itm['mod_time'] = mod_time
            except:
                pass

            yield itm

        elif cate == 'live-updates':
            try:
                data = json.loads(response.xpath('//script[@type="application/ld+json"]/text()').extract_first())
                content = data['articleBody']
                itm['content'] = content.replace('. ', '.\n').replace('  ', '\n')

                if not itm.get('images') and data.get('image'):
                    img_url = data['image'].get('url') or ''
                    if img_url:
                        img_caption = ''
                        img_time = ''
                        images = [
                            {'url': img_url, 'caption': img_caption, 'img_time': img_time}
                        ]
                        images = images
                        itm['images'] = images

                mod_time = self.to_utc_string(data.get('dateModified') or '')
                if mod_time:
                    itm['mod_time'] = mod_time
            except:
                itm['content'] = ''
            if not itm['content']:
                itm['content'] = 'content'

            yield itm


    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def match_invalid_url(self, url):
        try:
            cate = re.search('https://www.politico.com/(\S+?)/', url).group(1)
            if cate in ['newsletters', 'live-updates', 'news']:
                return False
            return True
        except:
            return True

    def parse(self, response):
        if response.request.url == self.start_urls[0]:
            response.selector.remove_namespaces()
            for itm in response.xpath('//url'):
                url = itm.xpath('./loc/text()').extract_first('')
                if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                    continue
                cate = re.search('https://www.politico.com/(\S+?)/', url).group(1)  # 'newsletters', 'live-updates', 'news'
                title = itm.xpath('./news/title/text()').extract_first('')
                if not title:
                    continue
                pub_time = self.to_utc_string(itm.xpath('./news/publication_date/text()').extract_first(''))
                if not pub_time:
                    continue
                # 检查过期资讯并过滤
                if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                    self.logger.info(f'新闻过期：{pub_time}|{url}')
                    continue

                mod_time = ''
                desc = ''
                lang = itm.xpath('./news/publication/language/text()').extract_first('')
                content = ''
                source = itm.xpath('./news/publication/name/text()').extract_first('')
                keywords = ''

                img_url = itm.xpath('./image/loc/text()').extract_first('')
                if img_url:
                    img_caption = itm.xpath('./image/title/text()').extract_first('')
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
                impersonate = random.choice(self.IMPERSONATE_LIST)
                yield scrapy.Request(url, meta={
                    'snapshot': True, 'item': itm, 'detail': True, 'cate': cate,
                    'use_curl_cffi': True, 'curl_cffi_impersonate': impersonate
                }, callback=self.parse_detail, errback=self.parse_detail_failed)
