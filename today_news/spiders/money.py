import re
import os
import scrapy
import datetime
from urllib import parse
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class MoneySpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "经济日报"
    start_urls = ["https://money.udn.com/sitemap/gnews/1001"]

    def clean_txt(self, txt):
        return txt.strip().replace('<![CDATA[', '').replace(']]>', '').strip()

    def parse_detail(self, response):
        itm = response.meta["item"]

        d1 = response.xpath('//node()[@id="article_body"]')
        clean_text = d1.xpath('.//h1 | .//h2 | .//p').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p:
                # print([_p])
                if "$(document)" in _p:
                    _p = re.sub(r'\$\(document\).*$', '', _p, flags=re.DOTALL)
                txt_list.append(_p)
        # print('\n'.join(txt_list))
        itm["content"] = "\n".join(txt_list)
        if not itm["content"]:
            itm["content"] = "content"

        if not itm.get('images'):
            img_list = response.xpath('//figure[@class="photo_center"]//img')
            if img_list:
                img_url = img_list[0].xpath('./@src').extract_first('')
                img_caption = img_list[0].xpath('./@title').extract_first('')
                img_time = ''
                images = [
                    {'url': img_url, 'caption': img_caption, 'img_time': img_time}
                ]
                images = images
            else:
                images = []
            itm['images'] = images

        try:
            mod_time = re.search('"dateModified" ?: ?"(.*?)"', response.text).group(1)
            mod_time = self.to_utc_string(self.name, mod_time)
            if mod_time:
                itm['mod_time'] = mod_time
        except:
            pass

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

    def parse_target_site(self, response):
        response.selector.remove_namespaces()
        for itm in response.xpath("//url"):
            url = itm.xpath('./loc/text()').extract_first('')
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = self.clean_txt(itm.xpath('./news/title/text()').extract_first(''))
            if not title:
                continue
            pub_time = self.to_utc_string(self.name, itm.xpath('./news/publication_date/text()').extract_first(''))
            if not pub_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                continue

            source = itm.xpath('./news/publication/name/text()').extract_first('')
            desc = ''
            lang = itm.xpath('./news/publication/language/text()').extract_first('')
            content = ''
            keywords = self.clean_txt(itm.xpath('./news/keywords/text()').extract_first(''))

            mod_time = ''
            images = []
            desc = ""
            content = ""

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
            yield scrapy.Request(
                url,
                meta={"snapshot": True, "item": itm, "detail": True},
                callback=self.parse_detail,
                errback=self.parse_detail_failed,
            )

    def parse(self, response):
        if response.request.url == self.start_urls[0]:
            response.selector.remove_namespaces()
            for link in response.xpath("//loc/text()").extract():
                if re.match('https://money.udn.com/sitemap/news_contents/1001/\d+', link):
                    yield scrapy.Request(link, callback=self.parse_target_site)
