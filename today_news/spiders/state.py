import re
import os
import scrapy
import datetime
from urllib import parse
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class StateSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "美国国务院"
    # allowed_domains = ["state.gov"]
    start_urls = ["https://www.state.gov/sitemap_index.xml"]

    def parse_detail(self, response):
        itm = response.meta['item']
        d1 = response.xpath('//div[@class="entry-content"]//div[@class="wp-block-paragraph"]')
        clean_text = d1.xpath('.//p').xpath('string(.)')
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

        title = response.xpath(
            '//title/text()').extract_first('').rstrip(' - United States Department of State')
        if title:
            itm['title'] = title

        desc = response.xpath('//meta[@property="og:description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        if not itm.get('images'):
            img_list = response.xpath('//div[@class="entry-content"]//figure//img')
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
            itm['images'] = images

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse_target_site(self, response):
        response.selector.remove_namespaces()
        for itm in response.xpath('//url'):
            url = itm.xpath('./loc/text()').extract_first('')
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            mod_time = self.to_utc_string(self.name, itm.xpath('./lastmod/text()').extract_first(''))
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(mod_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{mod_time}|{url}')
                continue

            pub_time = mod_time
            desc = ''
            lang = ''
            content = ''
            source = ''
            title = ''
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
            yield scrapy.Request(url, meta={'snapshot': True, 'item': itm, 'detail': True},
                                 callback=self.parse_detail, errback=self.parse_detail_failed)

    def parse(self, response):
        if response.request.url == self.start_urls[0]:
            response.selector.remove_namespaces()
            lis = []
            for link in response.xpath('//loc/text()').extract():
                if link and '/page-sitemap' in link:
                    if link == 'https://www.state.gov/page-sitemap.xml':
                        x = 0
                        lis.append((link, x))
                    else:
                        try:
                            # https://www.state.gov/page-sitemap209.xml
                            x = int(re.search(r'/page-sitemap(\d+).xml', link).group(1))
                            lis.append((link, x))
                        except:
                            continue
            print('处理', sorted(lis, key=lambda x: x[1], reverse=True)[:2])
            for url_itm in sorted(lis, key=lambda x: x[1], reverse=True)[:2]:
                yield scrapy.Request(url_itm[0], callback=self.parse_target_site)
