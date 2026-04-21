import scrapy
import re
import html
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered

class JTBCFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "JTBC新闻"
    allowed_domains = ["jtbc.co.kr"]
    start_urls = ["https://news.jtbc.co.kr/sitemaps/latest-articles"]

    def parse_detail(self, response):
        itm = response.meta['item']

        # 去除div各种标签, 保留文本
        clean_text = response.xpath('//data/articlecontent').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            # 去除HTML标签
            _p = remove_tags(p)
            _p = self.clean_phrase(_p)
            if _p:
                # print([_p])
                txt_list.append(_p)
        # print('\n'.join(txt_list))
        itm['content'] = '\n'.join(txt_list)
        if not itm['content']:
            itm['content'] = 'content'

        desc = response.xpath('//data/articlevideoviewinnertext/text()').extract_first('')
        if desc:
            itm['desc'] = desc

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
            url = response.urljoin(itm.xpath('./loc/text()').extract_first(''))
            url = url.replace('https://news.jtbc.co.kr/article/', 'https://news-api.jtbc.co.kr/v2/get/article/') + '?'
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = itm.xpath('./news/title/text()').extract_first('')
            if title:
                title = title.replace('![CDATA[', '').replace(']]>', '')
            pub_time = self.to_utc_string(self.name,itm.xpath('./news/publication_date/text()').extract_first(''))
            if not pub_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                continue

            mod_time = self.to_utc_string(self.name,itm.xpath('./lastmod/text()').extract_first(''))
            desc = ''
            lang = itm.xpath('./news/publication/language/text()').extract_first('')
            content = ''
            source = itm.xpath('./news/publication/name/text()').extract_first('')
            keywords = itm.xpath('./news/keywords/text()').extract_first('')
            if keywords:
                keywords = keywords.replace('![CDATA[', '').replace(']]>', '')
            images = [
                {
                    'url': itm.xpath('./image/loc/text()').extract_first(''),
                    'caption': '',
                    'img_time': ''
                }
            ]

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