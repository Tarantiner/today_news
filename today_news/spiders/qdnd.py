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


class QdndSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "人民军队报"
    # allowed_domains = ["qdnd.vn"]
    start_urls = ["https://www.qdnd.vn/sitemaps/0/top300article.xml"]

    def parse_detail(self, response):
        itm = response.meta['item']

        title = self.clean_phrase(response.xpath("//title/text()").extract_first(""))
        if not title:
            return
        itm["title"] = title

        try:
            pub_time = self.to_utc_string(self.name, re.search('"datePublished": ?"(.*?)"', response.text).group(1))
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

        d1 = response.xpath('//div[@itemprop="articleBody"]')
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

        # if not itm.get('images'):
        #     img_list = response.xpath('//picture[contains(@data-crop, "crop")]//img')
        #     if img_list:
        #         img_url = img_list[0].xpath('./@src').extract_first('')
        #         img_caption = img_list[0].xpath('./@alt').extract_first('')
        #         img_time = ''
        #         images = [
        #             {'url': img_url, 'caption': img_caption, 'img_time': img_time}
        #         ]
        #         images = images
        #     else:
        #         images = []
        #     itm['images'] = images

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
                mod_time = self.to_utc_string(self.name, itm.xpath('./lastmod/text()').extract_first(''))
                if not mod_time:
                    continue
                # 检查过期资讯并过滤
                if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(mod_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                    self.logger.info(f'新闻过期：{mod_time}|{url}')
                    continue

                img_list = itm.xpath('./image')
                if img_list:
                    img_url = img_list[0].xpath('./loc/text()').extract_first('')
                    img_caption = img_list[0].xpath('./title/text()').extract_first('')
                    img_time = ''
                    images = [
                        {'url': img_url, 'caption': img_caption, 'img_time': img_time}
                    ]
                    images = images
                else:
                    images = []

                pub_time = ''
                title = ''
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
                                     callback=self.parse_detail, errback=self.parse_detail_failed)
