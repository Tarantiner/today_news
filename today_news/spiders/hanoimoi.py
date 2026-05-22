import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class HanoimoiSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "首都劳动报"
    # allowed_domains = ["hanoimoi.vn"]
    start_urls = ["https://hanoimoi.vn/tin-moi-nhat"]

    async def start(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse_first_page,
                meta={'use_curl_cffi': True}
            )

    def parse_detail(self, response):
        itm = response.meta["item"]

        title = response.xpath('//meta[@itemprop="headline"]/@content').extract_first(
            ""
        )
        if title:
            itm["title"] = title

        pub_time_str = response.xpath(
            '//meta[@property="article:published_time"]/@content'
        ).extract_first("")
        if pub_time_str:
            pub_time = self.to_utc_string(self.name, pub_time_str)
            itm["pub_time"] = pub_time
            if self.settings.get("ENABLE_NEWS_TIME_FILTER") and self.check_expire_news(
                pub_time, self.settings.get("NEWS_EXPIRE_DAYS")
            ):
                self.logger.info(f"新闻过期：{pub_time}|{response.url}")
                return

        mod_time = response.xpath(
            '//meta[@property="article:modified_time"]/@content'
        ).extract_first("")
        if mod_time:
            itm["mod_time"] = self.to_utc_string(self.name, mod_time)

        lang = response.xpath('//meta[@name="language"]/@content').extract_first("")
        if lang:
            itm["lang"] = lang

        clean_text = response.xpath(
            '//div[@id="jtarticle"]/div[contains(@class, "article-body") and contains(@class, "blurred-text")]/p/text()'
        ) or response.xpath(
            '//div[@class="article-info"]/div[@class="article-body"]/p/text()'
        )
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

        source = response.xpath('//meta[@name="author"]/@content').extract_first("")
        if source:
            itm["source"] = source

        if not itm.get("images"):
            img_list = response.xpath('//meta[@itemprop="image"]')
            if img_list:
                img_url = img_list[0].xpath("./@content").extract_first("")
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

    def parse_first_page(self, response):
        pid_list = response.xpath("//li[@pid]/@pid").extract()
        try:
            max_pid = max(int(pid) for pid in pid_list)
            print(max_pid)
        except ValueError:
            self.logger.error(f"获取最大pid失败：{response.url}")
            return

        yield scrapy.Request(
            f'https://hanoimoi.vn/api/getMoreArticle/24h_empty_{max_pid}_0_0',
            callback=self.parse,
        )

    def parse(self, response):
        try:
            for itm in response.json():
                url = itm.get('LinktoMe2') or ''
                if not url:
                    continue
                if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                    continue
                title = itm.get('TitleIcon16') or ''
                if not title:
                    continue
                pub_time = self.to_utc_string(self.name, itm.get('TimeX2') or '' + '+07:00')
                if not pub_time:
                    continue
                # 检查过期资讯并过滤
                if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get(
                        'NEWS_EXPIRE_DAYS')):
                    self.logger.info(f'新闻过期：{pub_time}|{url}')
                    continue

                # is_origin = True if itm.get('thumbnails_type') == 'original' else False
                mod_time = ''
                desc = ''
                lang = ''
                content = ''
                source = ''
                keywords = ''

                img_url = itm.get('Thumbnail') or ''
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
        except Exception as e:
            self.logger.error(f"解析数据失败：{response.url}|{e}")
            return
