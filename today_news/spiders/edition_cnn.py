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


class EditionCNNSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "美国有线电视新闻网"
    allowed_domains = ["edition.cnn.com", "www.cnn.com", "media.cnn.com"]
    start_urls = ["https://edition.cnn.com/sitemap/news.xml"]

    def parse_detail(self, response):
        itm = response.meta['item']
        try:
            data = json.loads(response.xpath('//script[@type="application/ld+json"]/text()').extract_first())
            content_lis = [i for i in data if i['@type']=='NewsArticle']
            if content_lis:
                content = content_lis[0]['articleBody']
            else:
                content = ''
            if not content:
                content_itm_list = sorted([j for i in data if i['@type']=='LiveBlogPosting' for j in i['liveBlogUpdate']], key=lambda x: x['datePublished'])
                content_list = []
                for content_itm in content_itm_list:
                    _time = content_itm['datePublished']
                    _content = content_itm['articleBody'].rstrip('\n')
                    if not _content:
                        continue
                    content_list.append(f'{_time}:\n{_content}\n' if {_time} else f'{_content}\n')
                content = '\n'.join(content_list)
            itm['content'] = content
        except:
            itm['content'] = ''
        if not itm['content']:
            itm['content'] = 'content'

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

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
                if self.match_invalid_url(url):
                    continue
                title = itm.xpath('./news/title/text()').extract_first('')
                if not title:
                    continue
                pub_time = self.to_utc_string(itm.xpath('./news/publication_date/text()').extract_first(''))
                if not pub_time:
                    continue
                # 检查过期资讯并过滤
                if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                    self.logger.info(f'新闻过期：{pub_time}|{url}')
                    continue

                mod_time = self.to_utc_string(itm.xpath('./lastmod/text()').extract_first(''))
                desc = ''
                lang = itm.xpath('./news/publication/language/text()').extract_first('')
                content = ''
                source = itm.xpath('./news/publication/name/text()').extract_first('')
                keywords = ''

                img_url = itm.xpath('./image/loc/text()').extract_first('')
                if img_url:
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
