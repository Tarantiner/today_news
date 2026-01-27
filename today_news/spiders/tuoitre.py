import re
import os
import scrapy
import datetime
from urllib import parse
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class TuoitreSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "青年时代报"
    allowed_domains = ["tuoitre.vn"]
    start_urls = ["https://tuoitre.vn/sitemaps/latest-news.rss"]

    def clean_txt(self, txt):
        return txt.strip().replace('<![CDATA[', '').replace(']]>', '').strip()

    def parse_detail(self, response):
        itm = response.meta['item']
        pub_time = self.to_utc_string(response.xpath('//meta[@name="article:published_time"] | //meta[@property="article:published_time"]/@content').extract_first(''))
        if not pub_time:
            return
        # 检查过期资讯并过滤
        if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get(
                'NEWS_EXPIRE_DAYS')):
            self.logger.info(f'新闻过期：{pub_time}|{response.url}')
            return
        itm['pub_time'] = pub_time

        d1 = response.xpath('//div[contains(@class, "detail-content")]')
        clean_text = d1.xpath('./p').xpath('string(.)')
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

        if not itm.get('keywords'):
            itm['keywords'] = response.xpath('//meta[@name="keywords"]/@content').extract_first('')

        title = response.xpath(
            '//title/text()').extract_first('')
        if title:
            itm['title'] = title

        desc = response.xpath('//meta[@property="og:description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        try:
            itm['source'] = re.search('"publisher".*?"name": ?"(.*?)"', response.text, re.S).group(1)
        except:
            itm['source'] = ''

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
            title = os.path.basename(parse.urlparse(url.rstrip('.htm')).path)
            if not title:
                continue
            mod_time = self.to_utc_string(itm.xpath('./lastmod/text()').extract_first(''))
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(mod_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{mod_time}|{url}')
                continue

            pub_time = ''
            desc = ''
            lang = ''
            content = ''
            source = ''
            keywords = ''

            img_list = itm.xpath('./image')
            if img_list:
                img_url = img_list[0].xpath('./loc/text()').extract_first('')
                img_caption = self.clean_txt(img_list[0].xpath('./caption/text()').extract_first(''))
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

