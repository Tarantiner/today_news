import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class SputnikNewsFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "俄罗斯卫星通讯社"
    allowed_domains = ["sputniknews.cn", "cdn.sputniknews.cn"]
    start_urls = ["https://sputniknews.cn/news/"]

    def parse_detail(self, response):
        itm = response.meta['item']
        
        title = response.css('.container .article__title::text').extract_first('')
        if title:
            itm['title'] = title

        pub_time = response.xpath('//meta[@name="analytics:p_ts"]/@content').extract_first('')
        if pub_time:
            itm['pub_time'] = self.to_utc_string(self.name,pub_time)

        itm['mod_time'] = ''

        # .container .article__body .article__block .article__text::text或者.container .article__body .article__block .article__quote-text::text
        clean_text = response.css('.container .article__body .article__block .article__text::text, .container .article__body .article__block .article__quote-text::text')
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

        source = response.xpath('//meta[@name="analytics:author"]/@content').extract_first('')
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
            itm['keywords'] = response.xpath('//meta[@name="keywords"]/@content').extract_first('')

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
            for itm in response.css('div.list.list-tag a.list__title'):
                url = response.urljoin(itm.css('::attr(href)').extract_first(''))
                if not url:
                    continue
                if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                    continue
                title = ''
                pub_time = ''
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
