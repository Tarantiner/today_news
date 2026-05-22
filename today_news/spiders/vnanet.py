import re
import os
import scrapy
import datetime
import random
import traceback
from urllib import parse
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


# {'时政', '视频', '文化', '经济', '社会', '环保', '科技', '国际', ' 播客', '体育', '旅游', ' 图片'}
class VnanetSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "越南-越南通讯社"
    # allowed_domains = ["vnanet.vn"]

    IMPERSONATE_LIST = [
        "chrome110",
    ]

    async def start(self):
        base_url = "https://vnanet.vn/API/ApiGallery.ashx?func=getrawnews&index={}&limit=18&total=-1&cid=3&lid=1066"
        page = 0

        # 先请求第一页，用于判断是否继续
        first_url = base_url.format(page)

        impersonate = random.choice(self.IMPERSONATE_LIST)

        yield scrapy.Request(
            first_url,
            callback=self.parse_with_continuation,
            headers={
                "referer": "https://vnanet.vn/vi/tin/thoi-su-the-gioi-3/",
            },
            meta={
                "base_url": base_url,
                "current_page": page,
                "is_first": True,
                "use_curl_cffi": True,
                "curl_cffi_impersonate": impersonate,
            },
        )

    def match_invalid_url(self, cate):
        # {'tin-tuc', }
        return False
        # if cate in ('时政', '经济', '社会', '国际'):
        #     return False
        # return True

    def parse_detail(self, response):
        itm = response.meta["item"]
        d1 = response.xpath('//div[@class="post-content"]')
        clean_text = d1.xpath(".//p").xpath("string(.)")
        if not clean_text:
            clean_text = d1.xpath(".//div[contains(@class, 'ExternalClass')]").xpath("string(.)")
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p:
                for __p in _p.split("。  "):
                    __p = self.clean_phrase(__p)
                    if __p:
                        # print([__p])
                        txt_list.append(__p)
        # print('\n'.join(txt_list))
        itm["content"] = "\n".join(txt_list)
        if not itm["content"]:
            itm["content"] = "content"

        if not itm.get('images'):
            img_list = response.xpath('//article[contains(@class, "TextImgDetail")]//img')
            if img_list:
                img_url = img_list[0].xpath('./@content').extract_first('')
                img_caption = ''
                img_time = ''
                images = [
                    {'url': img_url, 'caption': img_caption, 'img_time': img_time}
                ]
                images = images
            else:
                images = []
            itm['images'] = images

        desc = response.xpath('//meta[@name="Description"]/@content').extract_first("")
        if desc:
            itm["desc"] = desc

        if not itm.get("keywords"):
            itm["keywords"] = response.xpath(
                '//meta[@name="Keywords"]/@content'
            ).extract_first("")

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse_with_continuation(self, response):
        base_url = response.meta["base_url"]
        current_page = response.meta["current_page"]
        is_first = response.meta.get("is_first", False)
        should_continue = True

        try:
            for itm in response.json()["data"]["data"]:
                url = str(itm.get("ID") or "")
                if not url:
                    continue
                url = parse.urljoin("https://vnanet.vn/vi/xem-tin-chi-tiet/", url)
                cate = (itm.get("zone") or {}).get("name") or ""
                if self.settings.get(
                    "ENABLE_NEWS_URL_FILTER"
                ) and self.match_invalid_url(cate):
                    continue
                title = self.clean_phrase(itm.get("Title") or "")
                if not title:
                    continue
                pub_time = self.to_utc_string(self.name, (itm.get("PublishDate") or "") + " +07:00")
                # 检查过期资讯并过滤
                if self.settings.get(
                    "ENABLE_NEWS_TIME_FILTER"
                ) and self.check_expire_news(
                    pub_time, self.settings.get("NEWS_EXPIRE_DAYS")
                ):
                    self.logger.info(f"新闻过期：{pub_time}|{url}")
                    if should_continue:
                        should_continue = False
                    continue

                mod_time = self.to_utc_string(self.name, (itm.get("Modified") or "") + " +07:00")
                desc = ""
                lang = ""
                content = ""
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

                impersonate = random.choice(self.IMPERSONATE_LIST)
                yield scrapy.Request(
                    url,
                    meta={
                        "snapshot": True,
                        "item": itm,
                        "detail": True,
                        "use_curl_cffi": True,
                        "curl_cffi_impersonate": impersonate,
                    },
                    headers={
                        "referer": "https://vnanet.vn/vi/tin/thoi-su-the-gioi-3/",
                    },
                    callback=self.parse_detail,
                    errback=self.parse_detail_failed,
                )
        except Exception as e:
            self.logger.error(f"解析内容异常|{traceback.format_exc()}")
            return

        if should_continue:
            next_page = current_page + 18
            next_url = base_url.format(next_page)
            print("继续访问", next_url)

            impersonate = random.choice(self.IMPERSONATE_LIST)
            yield scrapy.Request(
                next_url,
                callback=self.parse_with_continuation,
                headers={
                    "referer": "https://vnanet.vn/vi/tin/thoi-su-the-gioi-3/",
                },
                meta={
                    "base_url": base_url,
                    "current_page": next_page,
                    "is_first": False,
                    "use_curl_cffi": True,
                    "curl_cffi_impersonate": impersonate,
                },
            )
        else:
            print("应当停止", response.url)
