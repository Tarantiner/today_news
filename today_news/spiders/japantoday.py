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


class JapanTodaySpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "今日日本"
    allowed_domains = ["japantoday.com"]
    start_urls = [
        "https://japantoday.com/category/world"
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
        d1 = response.xpath('//div[@itemprop="articleBody"]')
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

    def parse_with_continuation(self, response):
        base_url = response.meta['base_url']
        current_page = response.meta['current_page']
        is_first = response.meta.get('is_first', False)
        response.selector.remove_namespaces()
        should_continue = True

        for itm in response.xpath('//div[contains(@class, "media media-")]'):
            url = itm.xpath('.//h3[contains(@class, "media-heading")]/a/@href').extract_first('')
            if not url:
                continue
            url = parse.urljoin('https://japantoday.com', url)
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = self.clean_phrase(
                itm.xpath('.//h3[contains(@class, "media-heading")]/a/@title').extract_first(''))
            if not title:
                continue
            pub_time = self.to_utc_string(itm.xpath('.//time[@itemprop="datePublished"]/@datetime').extract_first(''))
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get(
                    'NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                if should_continue:
                    should_continue = False
                continue

            mod_time = self.to_utc_string(itm.xpath('.//time[@itemprop="dateModified"]/@datetime').extract_first(''))
            desc = ''
            lang = ''
            content = ''
            source = ''
            keywords = ''

            img_list = itm.xpath('.//picture[@class="media-object"]//img')
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
