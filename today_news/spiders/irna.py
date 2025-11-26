import os
import scrapy
import datetime
from urllib import parse
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class IrnaSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "伊朗伊斯兰共和国通讯社"
    allowed_domains = ["irna.ir"]
    start_urls = [
        "https://en.irna.ir/sitemap/news/sitemap.xml",
        "https://zh.irna.ir/sitemap/news/sitemap.xml"
    ]

    # 统一utc时间字符串
    def parse_time(self, time_str):
        try:
            if not time_str:
                return ''
            format_time = datetime.datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%SZ').strftime("%Y-%m-%d %H:%M:%S")
            print(f'{time_str}==>{format_time}')
            return format_time
        except Exception as e:
            self.logger.info(f'转换时间失败:{type(e)}|{time_str}')
            return ''

    def parse_detail(self, response):
        d1 = response.xpath('//article[@id="item"]')
        d1 = response.xpath('//div[@class="item-body"]')
        clean_text = d1.xpath('.//p').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p == '更多 CTWANT 報導':
                continue
            if _p:
                txt_list.append(_p)
        itm = response.meta['item']
        # print('\n'.join(txt_list))
        itm['content'] = '\n'.join(txt_list)

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
        if response.request.url == 'https://en.irna.ir/sitemap/news/sitemap.xml':
            lang = 'en'
        elif response.request.url == 'https://zh.irna.ir/sitemap/news/sitemap.xml':
            lang = 'zh'
        else:
            return

        response.selector.remove_namespaces()
        for itm in response.xpath('//url'):
            url = itm.xpath('./loc/text()').extract_first('')
            if not url:
                continue
            if self.match_invalid_url(url):
                continue
            title = os.path.basename(parse.urlparse(url).path)
            if not title:
                continue
            pub_time = self.parse_time(itm.xpath('./news/lastmod/text()').extract_first(''))
            if not pub_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                continue

            mod_time = pub_time
            desc = ''
            lang = lang
            content = ''
            source = ''
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
