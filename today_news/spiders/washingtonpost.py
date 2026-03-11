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


class WashingtonPostSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "华盛顿邮报"
    allowed_domains = ["washingtonpost.com"]
    start_urls = ["https://www.washingtonpost.com/sitemaps/news-sitemap.xml.gz"]

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                meta={'use_curl_cffi': True}
            )

    def parse_detail(self, response):
        try:
            data = response.json()
        except:
            self.logger.error(f'解析json失败:|{response.url}')
            return

        itm = response.meta['item']

        desc = (data.get('description') or {}).get('basic') or ''
        if desc:
            itm['desc'] = desc

        txt_list = []
        for ii in data.get('content_elements') or []:
            if ii.get('type') in ('header', 'text'):
                _p = ii.get('content') or ''
                if _p:
                    # print([_p])
                    txt_list.append(remove_tags(_p))
        itm['content'] = '\n'.join(txt_list)
        if not itm['content']:
            itm['content'] = 'content'

        # if not itm.get('images'):
        #     img_url = response.xpath('//meta[@property="og:image"]/@content').extract_first('')
        #     if img_url:
        #         img_caption = ''
        #         img_time = ''
        #         images = [
        #             {'url': img_url, 'caption': img_caption, 'img_time': img_time}
        #         ]
        #         images = images
        #     else:
        #         images = []
        #     itm['images'] = images

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        full_news_url = 'https://www.washingtonpost.com/arc/prism/api/prism-content-api'
        headers = {
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0',
        }
        if response.request.url == self.start_urls[0]:
            response.selector.remove_namespaces()
            for itm in response.xpath('//url'):
                url = itm.xpath('./loc/text()').extract_first('')
                if not url:
                    continue
                if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                    continue
                title = itm.xpath('./news/title/text()').extract_first('')
                if not title:
                    continue
                pub_time = self.to_utc_string(self.name, itm.xpath('./news/publication_date/text()').extract_first(''))
                if not pub_time:
                    continue
                # 检查过期资讯并过滤
                if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                    self.logger.info(f'新闻过期：{pub_time}|{url}')
                    continue

                mod_time = self.to_utc_string(self.name, itm.xpath('./lastmod/text()').extract_first(''))
                desc = ''
                lang = itm.xpath('./news/publication/language/text()').extract_first('')
                content = ''
                source = itm.xpath('./news/publication/name/text()').extract_first('')
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
                url_path = parse.urlparse(url).path
                web_url = full_news_url + '?_website=washpost&query={"canonical_url":"' + url_path + '"}'
                yield scrapy.Request(web_url, meta={'snapshot': True, 'item': itm, 'detail': True}, headers=headers,
                                     callback=self.parse_detail, errback=self.parse_detail_failed)
