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


class RTISpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "中央广播电台"
    # allowed_domains = ["rti.org.tw"]
    start_urls = [
        "https://www.rti.org.tw/newscategorylist?&cid=1",  # 两岸
        "https://www.rti.org.tw/newscategorylist?&cid=3",  # 国际
        "https://www.rti.org.tw/newscategorylist?&cid=3",  # 政治
    ]

    def parse_detail(self, response):
        itm = response.meta['item']

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


        d1 = response.xpath('//div[@class="newsDetails"]/div[@class="left"]')
        clean_text = d1.xpath('.//p | .//h1 | .//h2 | .//h3 | .//h3 | .//h4').xpath('string(.)')
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

        try:
            mod_time = re.search('"dateModified" ?: ?"(.*?)"', response.text).group(1)
            mod_time = self.to_utc_string(self.name, mod_time)
            if mod_time:
                itm['mod_time'] = mod_time
        except:
            pass

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        if not itm.get('keywords'):
            itm['keywords'] = response.xpath('//meta[@name="keywords"]/@content').extract_first('')

        if not itm.get('images'):
            img_list = response.xpath('//div[@class="posImg"]/img')
            if img_list:
                img_url = response.urljoin(img_list[0].xpath('./@src').extract_first(''))
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
            itm['keywords'] = ','.join(response.xpath('//meta[@name="keywords"]/@content').extract())

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        # base_url = response.meta['base_url']
        # current_page = response.meta['current_page']
        # is_first = response.meta.get('is_first', False)
        # response.selector.remove_namespaces()
        # should_continue = True

        for itm in response.xpath('//div[@class="warpList"]//div[@class="item"]'):
            url = itm.xpath('./a/@href').extract_first('')
            if not url:
                continue
            url = parse.urljoin('https://www.rti.org.tw', url)
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = self.clean_phrase(
                itm.xpath('.//div[contains(@class, "title")]').xpath('string(.)').extract_first(''))
            if not title:
                continue

            pub_time = ""
            mod_time = ""
            desc = ''
            lang = ''
            content = ''
            source = ''
            keywords = ''

            img_list = itm.xpath('.//div[@class="img"]//img')
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

