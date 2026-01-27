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


class VtvSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "越南国家电视台"
    allowed_domains = ["vtv.vn"]
    start_urls = ["https://vtv.vn/the-gioi/tin-tuc.htm"]

    def clean_txt(self, txt):
        return txt.strip().replace('<![CDATA[', '').replace(']]>', '').strip()

    def parse_detail(self, response):
        itm = response.meta['item']
        try:
            pub_time = self.to_utc_string(re.search('"datePublished": ?"(.*?)"', response.text).group(1))
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

        try:
            mod_time = re.search('"dateModified" ?: ?"(.*?)"', response.text).group(1)
            mod_time = self.to_utc_string(mod_time)
            if mod_time:
                itm['mod_time'] = mod_time
        except:
            pass

        lang = response.xpath('//meta[@name="Language"]/@content').extract_first('')
        if not itm.get('lang') and lang:
            itm['lang'] = lang

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if not itm.get('desc') and desc:
            itm['desc'] = desc

        if not itm.get('keywords'):
            itm['keywords'] = response.xpath('//meta[@name="news_keywords"]/@content').extract_first('')

        if not itm.get('lang'):
            itm['lang'] = response.xpath('//meta[@name="lang"]/@content').extract_first('')

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        for itm in response.xpath('//div[@class="box-category-item"]'):
            url = itm.xpath('.//a[@data-type="title"]/@href').extract_first('')
            if not url:
                continue
            url = parse.urljoin('https://vtv.vn/', url)
            title = itm.xpath('.//a[@data-type="title"]/text()').extract_first('').strip('\r\n ')
            if not title:
                continue
            desc = itm.xpath('.//div[@data-type="sapo"]/text()').extract_first('').strip('\r\n ')

            pub_time = ''
            mod_time = ''
            lang = ''
            content = ''
            keywords = ''
            source = ''

            img_list = itm.xpath('.//img[@data-type="avatar"]')
            if img_list:
                img_url = img_list[0].xpath('./@src').extract_first('')
                # img_caption不准确
                img_caption = ''
                # img_caption = self.clean_txt(img_list[0].xpath('./@alt').extract_first(''))
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