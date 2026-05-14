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


class UyghurnetSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "维吾尔新闻研究中心"
    start_urls = ["https://www.uyghurnet.org/kategori/tum-mansetler/"]

    def clean_txt(self, txt):
        return txt.strip().replace('<![CDATA[', '').replace(']]>', '').strip()

    def parse_detail(self, response):
        itm = response.meta['item']
        try:
            pub_time = self.to_utc_string(self.name, response.xpath('//meta[@property="article:published_time"]/@content').extract_first(''))
        except:
            return
        if not pub_time:
            return
        # 检查过期资讯并过滤
        if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get(
                'NEWS_EXPIRE_DAYS')):
            self.logger.info(f'新闻过期：{pub_time}|{response.url}')
            return
        itm['pub_time'] = pub_time

        d1 = response.xpath('//div[@class="haber"]')
        clean_text = d1.xpath('.//p').xpath('string(.)')
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

        try:
            mod_time = response.xpath('//meta[@property="article:modified_time"]/@content').extract_first('')
            mod_time = self.to_utc_string(self.name, mod_time)
            if mod_time:
                itm['mod_time'] = mod_time
        except:
            pass

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if not itm.get('desc') and desc:
            itm['desc'] = desc

        img_list = response.xpath('//img[@class="aligncenter"]')
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

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        for itm in response.xpath('//ul[@class="konular"]/li'):
            url = itm.xpath('./a/@href').extract_first('')
            if not url:
                continue
            title = itm.xpath('./a/p/text()').extract_first('')
            if not title:
                continue

            pub_time = ''
            mod_time = ''
            lang = ''
            content = ''
            keywords = ''
            source = ''
            desc = ''
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