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


class NHKSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "NHK"
    allowed_domains = ["nhk.org.jp", "www3.nhk.or.jp"]
    start_urls = [
        "https://www3.nhk.or.jp/nhkworld/data/en/news/all.json",
    ]

    def parse_detail(self, response):
        itm = response.meta['item']
        try:
            content = json.loads(response.xpath('//script[@type="application/ld+json"]/text()').extract_first())[
                           'articleBody']
            itm['content'] = content.replace('. ', '.\n').replace('  ', '\n')
        except:
            itm['content'] = ''
        if not itm['content']:
            itm['content'] = 'content'

        # # 该网站关键词都是一样的，没有参考意义
        # if not itm.get('keywords'):
        #     itm['keywords'] = response.xpath('//meta[@name="keywords"]/@content').extract_first('')

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        try:
            for itm in response.json()['data']:
                url = itm.get('page_url') or ''
                if not url:
                    continue
                if self.match_invalid_url(url):
                    continue
                url = parse.urljoin('https://www3.nhk.or.jp', url)
                title = itm.get('title') or ''
                if not title:
                    continue
                pub_time = self.to_utc_string(itm.get('updated_at') or '')
                if not pub_time:
                    continue
                # 检查过期资讯并过滤
                if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get(
                        'NEWS_EXPIRE_DAYS')):
                    self.logger.info(f'新闻过期：{pub_time}|{url}')
                    continue

                # is_origin = True if itm.get('thumbnails_type') == 'original' else False
                mod_time = ''
                desc = itm.get('description') or ''
                lang = ''
                content = ''
                source = ''
                keywords = ''

                img_info = itm.get('thumbnails') or {}
                img_url = img_info.get('small') or img_info.get('middle') or img_info.get('large') or ''
                if img_url:
                    img_url = parse.urljoin('https://www3.nhk.or.jp', img_url)
                    img_caption = img_info.get('alt') or img_info.get('caption') or ''
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
        except:
            self.logger.error(f'解析新闻列表失败|{traceback.format_exc()}')


