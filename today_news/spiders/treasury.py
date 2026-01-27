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


class TreasurySpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "外国资产控制办公室"
    allowed_domains = ["ofac.treasury.gov"]
    start_urls = [
        "https://ofac.treasury.gov/recent-actions?page=0",
        "https://ofac.treasury.gov/recent-actions?page=1",
    ]

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                headers={
                    'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                    'sec-fetch-dest': 'document',
                    'sec-fetch-mode': 'navigate',
                    'sec-fetch-site': 'none',
                    'sec-fetch-user': '?1',
                    'upgrade-insecure-requests': '1',
                },
            )

    def parse_detail(self, response):
        itm = response.meta['item']
        d1 = response.xpath('//div[contains(@class, "field--name-field-body")]/div[@class="field__item"]')
        clean_text = d1.xpath('./p | ./h1 | ./h2 | ./h3 | ./h4').xpath('string(.)')
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

    def parse(self, response):
        for itm in response.xpath('//div[@class="view-content"]//div[contains(@class, "search-result")]'):
            url = itm.xpath('.//a[@hreflang]/@href').extract_first('')
            if not url:
                continue
            if not url.startswith('http'):
                url = parse.urljoin('https://ofac.treasury.gov', url)
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = itm.xpath('.//a[@hreflang]/text()').extract_first('')
            if not title:
                continue

            pub_time = self.to_utc_string(itm.xpath('./div[2]/div/text()').extract_first('').strip(' -   \n').strip())
            if not pub_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                continue

            mod_time = ''
            desc = ''
            lang = ''
            content = ''
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
                                 callback=self.parse_detail, errback=self.parse_detail_failed,
                                 headers={
                                     'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
                                     'sec-ch-ua-mobile': '?0',
                                     'sec-ch-ua-platform': '"Windows"',
                                     'sec-fetch-dest': 'document',
                                     'sec-fetch-mode': 'navigate',
                                     'sec-fetch-site': 'none',
                                     'sec-fetch-user': '?1',
                                     'upgrade-insecure-requests': '1',
                                 })
