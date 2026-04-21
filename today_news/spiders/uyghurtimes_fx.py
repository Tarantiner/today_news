import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class UyghurTimesFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "维吾尔时报"
    allowed_domains = ["uyghurtimes.com", "weiwuer.com"]
    start_urls = ["https://cn.uyghurtimes.com/wp-sitemap-posts-post-1.xml"]

    def parse_detail(self, response):
        itm = response.meta['item']

        itm['title'] = response.xpath('//article//div[@class="entry-header-details"]//h1[@class="entry-title"]/text()').extract_first('')
        if not itm['title']:
            itm['title'] = response.xpath('//title/text()').extract_first('')

        clean_text = response.xpath('//article//div[@class="entry-content"]//text()')
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

        desc = response.xpath('//article//div[@class="entry-header-details"]//div[@class="post-excerpt"]/p/text()').extract_first('')
        if desc:
            itm['desc'] = desc

        source = response.xpath('//article//div[@class="entry-header-details"]//span[contains(@class, "posts-author")]/a/text()').extract_first('')
        if source:
            itm['source'] = source

        if not itm.get('images'):
            img_list = response.xpath('//article//div[contains(@class, "post-thumbnail")]//img')
            if img_list:
                img_url = response.urljoin(img_list[0].xpath('./@src').extract_first(''))
                img_caption = img_list[0].xpath('./@alt').extract_first('')
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
        # print(response.text)
        for itm in response.xpath('//url'):
            url = response.urljoin(itm.xpath('./loc/text()').extract_first(''))
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = ''
            pub_time = self.to_utc_string(self.name,itm.xpath('./lastmod/text()').extract_first(''))
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
