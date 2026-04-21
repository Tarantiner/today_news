import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class ImbcFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "MBC新闻"
    allowed_domains = ["imbc.com"]
    start_urls = [f"https://imnews.imbc.com/replay/{datetime.datetime.now().year}/nwtoday/#page=1",f"https://imnews.imbc.com/replay/{datetime.datetime.now().year}/nwtoday/#page=2",f"https://imnews.imbc.com/replay/{datetime.datetime.now().year}/nwtoday/#page=3"]

    def parse_detail(self, response):
        itm = response.meta['item']

        pub_time_str = response.xpath('//meta[@name="nextweb:createDate"]/@content').extract_first('')
        if pub_time_str:
            pub_time = self.to_utc_string(self.name,pub_time_str)
            itm['pub_time'] = pub_time
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{response.url}')
                return

        mod_time_str = response.xpath('//meta[@name="nextweb:modDate"]/@content').extract_first('')
        if mod_time_str:
            mod_time = self.to_utc_string(self.name,mod_time_str)
            itm['mod_time'] = mod_time

        clean_text = response.xpath('//*[@id="content"]/div//article//div[@class="news_txt"]//text()')
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
        response.selector.remove_namespaces()
        for itm in response.xpath('//*[@id="content"]/section//div[contains(@class, "list_bottom")]/ul/li'):
            url = response.urljoin(itm.xpath('./a/@href').extract_first(''))
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = itm.xpath('./a/span[@class="txt_w"]/span[contains(@class, "tit")]/text()').extract_first('')
            pub_time = ''

            mod_time = ''
            desc = itm.xpath('./a/span[@class="txt_w"]/span[contains(@class, "sub")]/text()').extract_first('')
            lang = ''
            content = ''
            source = itm.xpath('./a/span[@class="txt_w"]/span[contains(@class, "sub2")]/span/text()').extract_first('')
            keywords = ''
            images = [
                {
                    'url': itm.xpath('./a/span[contains(@class, "img")]/img/@src').extract_first(''),
                    'caption': itm.xpath('./a/span[contains(@class, "img")]/img/@alt').extract_first(''),
                    'img_time': ''
                }
            ]

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