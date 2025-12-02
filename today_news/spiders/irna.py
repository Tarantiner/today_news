import os
import re
import execjs
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
        # "https://zh.irna.ir/sitemap/news/sitemap.xml"  # 中文好像和英文内容一样，翻译过的
    ]

    def parse_cookies(self, response):
        js = """run = function(x){
          return eval(x)
        }"""
        try:
            ctx = execjs.compile(js)
            v1 = re.search("value_v1': eval\(\"(.*?)\"", response.text).group(1)
            v2 = re.search("value': eval\(\"(.*?)\"", response.text).group(1)
            __arcsjs = ctx.call('run', v1)
            __arcsjsc = ctx.call('run', v2)
            print('获取到__arcsjs', __arcsjs)
            print('获取到__arcsjsc', __arcsjsc)
            for url in self.start_urls:
                yield scrapy.Request(
                    url=url, cookies={'__arcsjs': __arcsjs, '__arcsjsc': __arcsjsc},
                    meta={'cookiejar': 'my_session'},
                    callback=self.parse, dont_filter=True
                )
        except:
            self.logger.error(f'未解析出cookie参数')
            return

    async def start(self):
        yield scrapy.Request(
            self.start_urls[0],
            callback=self.parse_cookies,
        )

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
        d1 = response.xpath('//div[@class="item-body"]')
        clean_text = d1.xpath('./div/p').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p:
                if _p == '本社讯- ':
                    continue
                # print([_p])
                txt_list.append(_p)
        if txt_list[-1] and re.match('^\d+\*\*\d+$', txt_list[-1]):
            txt_list.pop(-1)

        itm = response.meta['item']
        # print('\n'.join(txt_list))
        itm['content'] = '\n'.join(txt_list)
        if not itm['content']:
            itm['content'] = 'content'

        if not itm.get('keywords'):
            itm['keywords'] = response.xpath('//meta[@name="keywords"]/@content').extract_first('')

        if not itm.get('images'):
            img_url = response.xpath('//figure[@class="item-img"]//img/@src').extract_first('')
            if img_url:
                img_caption = response.xpath('//figure[@class="item-img"]//img/@alt').extract_first('')
                img_time = ''
                images = [
                    {'url': img_url, 'caption': img_caption, 'img_time': img_time}
                ]
                images = images
            else:
                images = []
            itm['images'] = images

        title = response.xpath('//meta[@name="twitter:title"]/@content').extract_first('')
        if title:
            itm['title'] = title

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        pub_time = self.parse_time(response.xpath('//meta[@property="article:published_time"]/@content').extract_first(''))
        if pub_time:
            itm['pub_time'] = pub_time
        mod_time = self.parse_time(response.xpath('//meta[@property="article:modified_time"]/@content').extract_first(''))
        if mod_time:
            itm['mod_time'] = mod_time

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        if response.request.url not in self.start_urls:
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
            pub_time = self.parse_time(itm.xpath('./lastmod/text()').extract_first(''))
            if not pub_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                continue

            mod_time = pub_time
            desc = ''
            lang = ''
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
                                 cookies=response.request.cookies,
                                 callback=self.parse_detail, errback=self.parse_detail_failed)
