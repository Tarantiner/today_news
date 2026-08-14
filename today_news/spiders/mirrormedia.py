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


class MirrormediaSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "镜传媒"
    # allowed_domains = ["news.cts.com.tw"]
    start_urls = ["https://www.mirrormedia.mg/rss/posts-news.xml"]

    def clean_txt(self, txt):
        return txt.strip().replace('<![CDATA[', '').replace(']]>', '').strip()

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

        try:
            s = response.xpath('//script[@type="application/ld+json"]/text()').extract_first('')
            _itm = json.loads(s)
            itm['content'] = _itm.get('articleBody') or ''
            desc = _itm.get('description') or ''
            if desc:
                itm['desc'] = desc
            keywords = _itm.get('keywords') or ''
            if keywords:
                itm['keywords'] = keywords
            img_url = _itm.get('image') or ''
            img_caption = ''
            img_time = ''
            images = [
                {'url': img_url, 'caption': img_caption, 'img_time': img_time}
            ]
            images = images
            itm['images'] = images
            if not itm['content']:
                itm['content'] = 'content'
            # desc = data['initialData']['data']['article']['summary']
        except:
            self.logger.warning(f'提取{response.url}内容失败')
            itm['content'] = 'content'

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
                url = itm.xpath('./loc/text()').extract_first('').replace('?utm_source=rss', '')
                if not url:
                    continue
                if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                    continue
                title = self.clean_txt(itm.xpath('./news/title/text()').extract_first(''))
                if not title:
                    continue
                mod_time = self.to_utc_string(self.name, itm.xpath('./lastmod/text()').extract_first(''))
                if not mod_time:
                    continue
                # 检查过期资讯并过滤
                if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(mod_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                    self.logger.info(f'新闻过期：{mod_time}|{url}')
                    continue

                pub_time = ''
                desc = self.clean_txt(itm.xpath('./description/text()').extract_first(''))
                lang = itm.xpath('./language/text()').extract_first('')
                content = ''
                source = itm.xpath('./news/publication/name/text()').extract_first('')
                keywords = self.clean_txt(itm.xpath('./news/keywords/text()').extract_first(''))
                img_list = itm.xpath('./image')
                if img_list:
                    img_url = img_list[0].xpath('./loc/text()').extract_first('')
                    img_caption = ''
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
