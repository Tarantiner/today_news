import scrapy
import re
import datetime
import pytz
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class AljazeeraFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "共同社"
    allowed_domains = ["kyodonews.net","ismcdn.jp"]
    start_urls = ["https://china.kyodonews.net/news/global_news","https://china.kyodonews.net/news/global_news?page=2","https://china.kyodonews.net/news/global_news?page=3"]

    def parse_detail(self, response):
        itm = response.meta['item']
        
        title = response.xpath('//meta[@property="og:title"]/@content').extract_first('')
        if title:
            itm['title'] = title

        clean_text = response.xpath('//div[@class="article-body__inner"]/p/text()')
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

        source = response.xpath('//meta[@name="application-name"]/@content').extract_first('')
        if source:
            itm['source'] = source

        if not itm.get('images'):
            img_list = response.xpath('//meta[@property="og:image"]')
            if img_list:
                img_url = response.urljoin(img_list[0].xpath('./@content').extract_first(''))
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
            itm['keywords'] = ''

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        response.selector.remove_namespaces()
        for itm in response.xpath('//article/div[@class="m-article-item__content"]'):
            url = response.urljoin(itm.xpath('./h3[@class="m-article-item-ttl"]/a/@href').extract_first(''))
            print(url)
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = ''
            pub_time = self.to_utc_string(self.name,itm.xpath('./div[@class="m-article-info"]/time/@datetime').extract_first('') + '+09:00')
            if not pub_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                continue
            mod_time = ''
            desc = ''
            lang = ''
            content = ''
            source = ''
            keywords = ''
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
