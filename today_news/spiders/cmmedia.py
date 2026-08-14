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


class CMMediaSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "信传媒"
    start_urls = [
        "https://www.cmmedia.com.tw/api/articles?num=12&page=1&category=politics",  # 政治
        "https://www.cmmedia.com.tw/api/articles?num=12&page=1&category=finance",  # 财经
        "https://www.cmmedia.com.tw/api/articles?num=12&page=1&category=global",  # 国际
    ]

    def parse_detail(self, response):
        itm = response.meta["item"]

        title = response.xpath("//title/text()").extract_first("")
        if not title:
            return
        itm["title"] = title

        pub_time_str = response.xpath('//meta[@itemprop="datePublished"]/@content').extract_first('')
        if pub_time_str:
            pub_time = self.to_utc_string(self.name,pub_time_str)
            itm['pub_time'] = pub_time
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{response.url}')
                return
        if not itm.get('pub_time'):
            return

        mod_time_str = response.xpath('//meta[@itemprop="dateModified"]/@content').extract_first('')
        if mod_time_str:
            mod_time = self.to_utc_string(self.name,mod_time_str)
            itm['mod_time'] = mod_time

        d1 = response.xpath('//div[@itemprop="articleBody"]')
        clean_text = d1.xpath('.//h1 | .//h2 | .//p').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p:
                # print([_p])
                txt_list.append(_p)
        # print('\n'.join(txt_list))
        itm["content"] = "\n".join(txt_list)
        if not itm["content"]:
            itm["content"] = "content"

        if not itm.get('images'):
            img_list = response.xpath('//a[@class="post-photo"]//img')
            if img_list:
                img_url = img_list[0].xpath('./@src').extract_first('')
                img_caption = ''
                img_time = ''
                images = [
                    {'url': img_url, 'caption': img_caption, 'img_time': img_time}
                ]
                images = images
            else:
                images = []
            itm['images'] = images

        if not itm.get('keywords'):
            itm['keywords'] = response.xpath('//meta[@name="keywords"]/@content').extract_first('')

        desc = response.xpath(
            '//meta[@property="og:description"]/@content'
        ).extract_first("")
        if desc:
            itm["desc"] = desc

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        try:
            for itm in response.json():
                _id = itm.get('id') or ''
                if not _id:
                    continue
                url = f'https://www.cmmedia.com.tw/home/articles/{_id}'
                if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                    continue
                title = itm.get('title') or ''
                if not title:
                    continue
                # pub_time = self.to_utc_string(self.name, itm.get('updated_at') or '')
                # if not pub_time:
                #     continue
                # # 检查过期资讯并过滤
                # if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get(
                #         'NEWS_EXPIRE_DAYS')):
                #     self.logger.info(f'新闻过期：{pub_time}|{url}')
                #     continue

                # is_origin = True if itm.get('thumbnails_type') == 'original' else False
                pub_time = ''
                mod_time = ''
                desc = ''
                lang = ''
                content = ''
                source = ''
                keywords = ''

                _img_url = itm.get('img') or ''
                if _img_url:
                    img_url = parse.urljoin('https://www.cmmedia.com.tw/', _img_url)
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
        except:
            self.logger.error(f'解析新闻列表失败|{traceback.format_exc()}')


