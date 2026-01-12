import re
import os
import scrapy
import datetime
from urllib import parse
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class TwzSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "TBS新闻"
    allowed_domains = ["tbs.co.jp", "ismcdn.jp"]
    start_urls = ["https://newsdig.tbs.co.jp/sitemap.xml"]

    async def start(self):
        base_url = 'https://newsdig.tbs.co.jp/list/genre/%E5%9B%BD%E9%9A%9B?page='
        page = 1

        # 先请求第一页，用于判断是否继续
        first_url = f'{base_url}{page}'
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
        d1 = response.xpath('//div[contains(@class, "article-body")]')
        clean_text = d1.xpath('./p').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p:
                for __p in _p.split('\n\n'):
                    __p = self.clean_phrase(__p)
                    if __p:
                        print([__p])
                        txt_list.append(__p)
        # if not txt_list:
        #     for p in d1.xpath('string(.)').extract_first('').split('\n'):
        #         _p = self.clean_phrase(p)
        #         if _p:
        #             # print([_p])
        #             txt_list.append(_p)
        itm = response.meta['item']
        # print('\n'.join(txt_list))
        itm['content'] = '\n'.join(txt_list)
        if not itm['content']:
            itm['content'] = 'content'

        if not itm.get('images'):
            img_url = response.xpath('//meta[@property="og:image"]/@content').extract_first('')
            if img_url:
                img_caption = ''
                img_time = ''
                images = [
                    {'url': img_url, 'caption': img_caption, 'img_time': img_time}
                ]
                images = images
            else:
                images = []
            itm['images'] = images

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        if not itm.get('keywords'):
            itm['keywords'] = response.xpath('//meta[@name="keywords"]/@content').extract_first('')

        try:
            itm['source'] = re.search('"Organization", ?"name": ?"(.*?)"', response.text).group(1)
        except:
            itm['source'] = ''

        try:
            mod_time = self.to_utc_string(re.search('dateModified": ?"(.*?)"', response.text).group(1))
            if mod_time:
                itm['mod_time'] = mod_time
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

        pre_url = 'https://newsdig.tbs.co.jp'
        for itm in response.xpath('//article[contains(@class, "-article-row")]'):
            url = itm.xpath('./a/@href').extract_first('')
            if not url:
                continue
            url = parse.urljoin(pre_url, url)
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = self.clean_phrase(itm.xpath('./a//node()[contains(@class,"article-content__title")]/text()').extract_first(''))
            if not title:
                continue
            pub_time = self.to_utc_string(itm.xpath('./a//time[@class="c-date"]/@datetime').extract_first(''))
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
            images = []

            # # 可以获取图片，但是缩略图，分辨率太低，如果具体新闻中获取图片又存在视频没有图片的问题
            # img_list = itm.xpath('./a//figure[contains(@class, "article-figure")]/img')
            # if img_list:
            #     img_url = img_list[0].xpath('./@src').extract_first('')
            #     img_caption = img_list[0].xpath('./@alt').extract_first('')
            #     img_time = ''
            #     images = [
            #         {'url': img_url, 'caption': img_caption, 'img_time': img_time}
            #     ]
            #     images = images
            # else:
            #     images = []

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
            next_url = f'{base_url}{next_page}'

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

    # def parse(self, response):
    #     if response.request.url == self.start_urls[0]:
    #         response.selector.remove_namespaces()
    #         lis = []
    #         for link in response.xpath('//loc/text()').extract():
    #             if link and 'sitemap' in link:
    #                 try:
    #                     x = re.search('newsdig.tbs.co.jp/common/files/sitemap-(\d+?)-(\d+?).xml', link)
    #                     lis.append((link, int(x.groups()[0] + x.groups()[1])))
    #                 except:
    #                     continue
    #         for url_itm in sorted(lis, key=lambda x: x[1], reverse=True)[:2]:
    #             return scrapy.Request(url_itm[0], callback=self.parse_target_site)
