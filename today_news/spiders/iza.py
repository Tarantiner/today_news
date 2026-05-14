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


class IzaSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "IZA新闻"
    # allowed_domains = ["iza.ne.jp"]
    start_urls = [
        "https://www.iza.ne.jp/feeds/sitemap-events/?outputType=xml&from=0",
        "https://www.iza.ne.jp/feeds/sitemap-politics/?outputType=xml&from=0",
        "https://www.iza.ne.jp/feeds/sitemap-economy/?outputType=xml&from=0",
        "https://www.iza.ne.jp/feeds/sitemap-world/?outputType=xml&from=0",
        "https://www.iza.ne.jp/feeds/sitemap-column/?outputType=xml&from=0",
    ]

    def parse_detail(self, response):
        itm = response.meta['item']
        title = response.xpath(
            '//title/text()').extract_first('')
        if not title:
            return
        itm['title'] = title

        pub_time = self.to_utc_string(self.name, response.xpath('//meta[@name="article:published_time"]/@content').extract_first(''))
        if not pub_time:
            return
        # 检查过期资讯并过滤
        if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get(
                'NEWS_EXPIRE_DAYS')):
            self.logger.info(f'新闻过期：{pub_time}|{response.url}')
            return
        itm['pub_time'] = pub_time

        d1 = response.xpath('//div[contains(@class, "article-body")]')
        clean_text = d1.xpath('.//p[@class="article-text "]').xpath('string(.)')
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
            img_list = response.xpath('//meta[@property="og:image"]')
            if img_list:
                img_url = img_list[0].xpath('./@content').extract_first('')
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
            itm['keywords'] = response.xpath('//meta[@name="news_keywords"]/@content').extract_first('')

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        response.selector.remove_namespaces()
        for itm in response.xpath('//url'):
            url = itm.xpath('./loc/text()').extract_first('')
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            mod_time = self.to_utc_string(self.name, itm.xpath('./lastmod/text()').extract_first(''))
            if not mod_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(mod_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{mod_time}|{url}')
                continue

            pub_time = ''
            title = ''
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
                                    callback=self.parse_detail, errback=self.parse_detail_failed)
