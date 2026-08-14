import re
import os
import scrapy
import datetime
from urllib import parse
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class BaoxaydungSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "越南建设报"
    # allowed_domains = ["baoxaydung.vn"]
    start_urls = ["https://baoxaydung.vn/sitemap.xml"]

    def clean_txt(self, txt):
        return txt.strip().replace('<![CDATA[', '').replace(']]>', '').strip()

    def parse_detail(self, response):
        itm = response.meta["item"]

        title = response.xpath("//title/text()").extract_first("")
        if not title:
            return
        itm["title"] = title

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

        d1 = response.xpath('//node()[@itemprop="articleBody"]')
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

    def parse_target_site(self, response):
        response.selector.remove_namespaces()
        for itm in response.xpath("//url"):
            url = itm.xpath("./loc/text()").extract_first("")
            if not url:
                continue
            if self.settings.get("ENABLE_NEWS_URL_FILTER") and self.match_invalid_url(
                url
            ):
                continue
            mod_time = self.to_utc_string(
                self.name, itm.xpath("./lastmod/text()").extract_first("")
            )
            # 检查过期资讯并过滤
            if self.settings.get("ENABLE_NEWS_TIME_FILTER") and self.check_expire_news(
                mod_time, self.settings.get("NEWS_EXPIRE_DAYS")
            ):
                self.logger.info(f"新闻过期：{mod_time}|{url}")
                continue

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

            pub_time = ""
            desc = ""
            lang = ""
            content = ""
            source = ""
            keywords = ""
            title = ""

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
            lis = []
            for link in response.xpath("//loc/text()").extract():
                if link and "bxd-sitemaps-" in link:
                    try:
                        # https://baoxaydung.vn/sitemaps/bxd-sitemaps-2026-5-6-10.xml
                        res = re.search("bxd-sitemaps-(\d+)-(\d+)-(\d+)-(\d+)\.xml", link)
                        x1 = (
                            res.group(2)
                            if len(res.group(2)) == 2
                            else "0" + res.group(2)
                        )
                        x2 = (
                            res.group(3)
                            if len(res.group(3)) == 2
                            else "0" + res.group(3)
                        )
                        lis.append((link, int(f"{res.group(1)}{x1}{x2}")))
                    except:
                        continue
            print("处理", sorted(lis, key=lambda x: x[1], reverse=True)[:2])
            for url_itm in sorted(lis, key=lambda x: x[1], reverse=True)[:2]:
                yield scrapy.Request(url_itm[0], callback=self.parse_target_site)
