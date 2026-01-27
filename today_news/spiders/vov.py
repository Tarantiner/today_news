import re
import os
import json
import scrapy
import datetime
import traceback
from urllib import parse
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class VovSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "越南之声"
    allowed_domains = ["vov.vn"]
    start_urls = ["https://vov.vn/sitemap.xml"]

    def match_invalid_url(self, url):
        if any(('/kinh-te/' in url, '/the-gioi/' in url, '/chinh-tri/' in url, '/quan-su-quoc-phong/' in url)):
            return False
        return True

    def parse_target_site(self, response):
        response.selector.remove_namespaces()
        for itm in response.xpath('//url'):
            url = itm.xpath('./loc/text()').extract_first('')
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = os.path.basename(parse.urlparse(url).path)
            if not title:
                continue
            mod_time = self.to_utc_string(itm.xpath('./lastmod/text()').extract_first(''))
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(mod_time, self.settings.get(
                    'NEWS_EXPIRE_DAYS')):
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
                img_caption = img_list[0].xpath('./caption/text()').extract_first('')
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

        d1 = response.xpath('//div[@class="row article-content"]')
        clean_text = d1.xpath('.//div[@class="text-long"]/p').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p:
                # print([_p])
                txt_list.append(_p)
        # print('\n'.join(txt_list))
        itm['content'] = '\n'.join(txt_list)
        if not itm['content']:
            itm['content'] = 'content'

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        keywords = response.xpath('//meta[@name="keywords"]/@content').extract_first('')
        if desc:
            itm['keywords'] = keywords

        title = response.xpath('//title/text()').extract_first('')
        if title:
            itm['title'] = title

        if not itm.get('images'):
            img_list = response.xpath('//meta[@property="og:image"]')
            if img_list:
                img_url = img_list[0].xpath('./@content').extract_first('')
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

    def parse(self, response):
        if 'window.location.href' in response.text:
            try:
                new_url = re.search('window.location.href="(.*?)"',
                                    response.xpath('//script/text()').extract_first('')).group(1)
                yield scrapy.Request(new_url, callback=self.parse)
            except:
                return
        else:
            if self.start_urls[0] in response.request.url:
                response.selector.remove_namespaces()
                lis = []
                for link in response.xpath('//loc/text()').extract():
                    try:
                        x = re.search('https://vov.vn/sitemaps/(\d+)/(\d+)/article.xml', link)
                        lis.append((link, int(x.groups()[0] + f'0{x.groups()[1]}' if len(x.groups()[1]) == 1 else x.groups()[0] + x.groups()[1])))
                    except:
                        continue
                for url_itm in sorted(lis, key=lambda x: x[1], reverse=True)[:2]:
                    yield scrapy.Request(url_itm[0], callback=self.parse_target_site)