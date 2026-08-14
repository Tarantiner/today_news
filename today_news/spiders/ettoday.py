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


class EttodayNewsSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "ETtoday新闻云"
    # allowed_domains = ["ettoday.net"]
    start_urls = ["https://www.ettoday.net/news-sitemap.xml"]
    special_headers = {
        # 'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        # 'accept-language': 'zh-CN,zh;q=0.9',
        # 'cache-control': 'no-cache',
        # 'pragma': 'no-cache',
        # 'priority': 'u=0, i',
        # 'sec-ch-ua': '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        # 'upgrade-insecure-requests': '1',
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    }

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    "use_curl_cffi": True,
                    "curl_cffi_impersonate": "chrome120",
                    "headers": self.special_headers,
                },
            )
            # yield scrapy.Request(url, callback=self.parse, headers=self.special_headers)

    def clean_txt(self, txt):
        return txt.strip().replace("<![CDATA[", "").replace("]]>", "").strip()

    def parse_detail(self, response):
        itm = response.meta["item"]
        try:
            mod_time = re.search('"dateModified" ?: ?"(.*?)"', response.text).group(1)
            mod_time = self.to_utc_string(self.name, mod_time)
            if mod_time:
                itm["mod_time"] = mod_time
        except:
            pass

        d1 = response.xpath('//div[@itemprop="articleBody"]')
        clean_text = d1.xpath(".//h1 | .//h2 | .//p").xpath("string(.)")
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

        desc = response.xpath('//meta[@name="description"]/@content').extract_first("")
        if desc:
            itm["desc"] = desc

        if not itm.get("images"):
            img_list = response.xpath('//meta[@property="og:image"]')
            if img_list:
                img_url = response.urljoin(
                    img_list[0].xpath("./@content").extract_first("")
                )
                img_caption = ""
                img_time = ""
                images = [
                    {"url": img_url, "caption": img_caption, "img_time": img_time}
                ]
                images = images
            else:
                images = []
            itm["images"] = images

        if not itm.get("keywords"):
            itm["keywords"] = response.xpath(
                '//meta[@name="keywords"]/@content'
            ).extract_first("")

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
            for itm in response.xpath("//url"):
                url = itm.xpath("./loc/text()").extract_first("")
                if not url:
                    continue
                if self.settings.get(
                    "ENABLE_NEWS_URL_FILTER"
                ) and self.match_invalid_url(url):
                    continue
                s = itm.extract()
                try:
                    title = re.search(r"<news:title>(.*?)</news:title>", s).group(1)
                    if not title:
                        continue
                    pub_time = re.search(
                        r"<news:publication_date>(.*?)</news:publication_date>", s
                    ).group(1)
                    pub_time = self.to_utc_string(self.name, pub_time)
                    if not pub_time:
                        continue
                    # 检查过期资讯并过滤
                    if self.settings.get(
                        "ENABLE_NEWS_TIME_FILTER"
                    ) and self.check_expire_news(
                        pub_time, self.settings.get("NEWS_EXPIRE_DAYS")
                    ):
                        self.logger.info(f"新闻过期：{pub_time}|{url}")
                        continue
                except:
                    continue

                mod_time = ""
                desc = ""
                try:
                    lang = re.search(r"<news:language>(.*?)</news:language>", s).group(
                        1
                    )
                except:
                    lang = ""
                content = ""
                try:
                    source = re.search(r"<news:name>(.*?)</news:name>", s).group(1)
                except:
                    source = ""
                keywords = ""
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
                yield scrapy.Request(
                    url,
                    meta={
                        "snapshot": True,
                        "item": itm,
                        "detail": True,
                        "use_curl_cffi": True,
                        "curl_cffi_impersonate": "chrome120",
                        "headers": self.special_headers,
                    },
                    callback=self.parse_detail,
                    errback=self.parse_detail_failed,
                )
