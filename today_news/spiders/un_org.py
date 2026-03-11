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


class UNOrgSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "联合国新闻"
    # allowed_domains = ["indsr.org"]
    start_urls = [
        'https://news.un.org/zh/news/region/global',
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

        d1 = response.xpath('//section[@class="section"]//div[contains(@class, "views-element-container")] | //section[contains(@class, "region-before-content")]//div[contains(@class, "views-element-container")]')
        clean_text = d1.xpath('.//p | .//h1 | .//h2 | .//h3 | .//h4 | .//h5 | .//h6').xpath('string(.)')
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

        if not itm.get('keywords'):
            itm['keywords'] = response.xpath('//meta[@name="keywords"]/@content').extract_first('')

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

        for itm in response.xpath('//div[@class="view-content"]/div[@class="views-row"]'):
            url = itm.xpath('.//h2[@class="node__title"]/a/@href').extract_first('')
            if not url:
                continue
            if not url.startswith('http'):
                url = parse.urljoin('https://news.un.org', url)
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = self.clean_phrase(
                itm.xpath('.//h2[@class="node__title"]/a/span/text()').extract_first(''))
            if not title:
                continue
            pub_time = self.to_utc_string(self.name, itm.xpath('.//div[@class="node__meta"]//time[@class="datetime"]/@datetime').extract_first(''))
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

            img_list = itm.xpath('.//div[@class="node__media"]//picture/img')
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

        if should_continue:
            next_page = current_page + 1
            next_url = f'{base_url}?page={next_page}'
            print('继续访问', next_url)
            yield scrapy.Request(
                next_url,
                callback=self.parse_with_continuation,
                meta={
                    'base_url': base_url,
                    'current_page': next_page,
                    'is_first': False
                }
            )
        else:
            print('应当停止', response.url)
    
    def parse(self, response):
        for itm in response.xpath('//div[@id="tabcontentlistnewslist2edi"]/div[contains(@class, "contentwrapper")]'):
            # url = itm.xpath('.//a[contains(@href, "information")]/@href').extract_first('')
            url = itm.xpath('./h2/a/@href').extract_first('')
            if not url:
                continue
            if not url.startswith('http'):
                url = parse.urljoin('https://news.mingpao.com', url)
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = self.clean_phrase(itm.xpath('./h2/a/text()').extract_first(''))
            if not title:
                continue

            try:
                pub_time = self.to_utc_string(self.name, itm.xpath('./h2/a/small[@class="datetime"]/script').extract_first('').split('\'')[1])
            except:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get(
                    'NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                continue

            img_list = itm.xpath('./figure/div[contains(@class, "imgLiquidNoFill")]/a')
            if img_list:
                img_url = img_list[0].xpath('./@href').extract_first('')
                if not img_url.startswith('http'):
                    url = parse.urljoin('https://news.mingpao.com', img_url)
                img_caption = img_list[0].xpath('./@title').extract_first('')
                img_time = ''
                images = [
                    {'url': img_url, 'caption': img_caption, 'img_time': img_time}
                ]
                images = images
            else:
                images = []

            mod_time = ''
            desc = ''
            lang = ''
            content = ''
            source = ''
            keywords = ''

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
                                 callback=self.parse_detail, errback=self.parse_detail_failed,
                                #  headers={
                                #      'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
                                #      'sec-ch-ua-mobile': '?0',
                                #      'sec-ch-ua-platform': '"Windows"',
                                #      'sec-fetch-dest': 'document',
                                #      'sec-fetch-mode': 'navigate',
                                #      'sec-fetch-site': 'none',
                                #      'sec-fetch-user': '?1',
                                #      'upgrade-insecure-requests': '1',
                                #  }
                                 )
