import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class WhiteHouseFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "白宫新闻"
    allowed_domains = ["www.whitehouse.gov"]
    start_urls = ["https://www.whitehouse.gov/news/","https://www.whitehouse.gov/news/page/2/","https://www.whitehouse.gov/news/page/3/"]

    def parse_detail(self, response):
        itm = response.meta['item']
        
        title = response.css('.wp-block-group .wp-block-post-content .wp-block-whitehouse-topper__headline::text').extract_first('')
        if title:
            itm['title'] = title

        pub_time_str = response.xpath('//meta[@property="article:published_time"]/@content').extract_first('')
        if pub_time_str:
            pub_time = self.to_utc_string(self.name,pub_time_str)
            itm['pub_time'] = pub_time
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{response.url}')
                return

        itm['mod_time'] = ''

        clean_text = response.css('.wp-block-group .wp-block-post-content p::text, .wp-block-group .wp-block-post-content li::text')
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

        source = response.xpath('//meta[@property="og:site_name"]/@content').extract_first('')
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
        if response.request.url == self.start_urls[0]:
            response.selector.remove_namespaces()
            for itm in response.css('.wp-block-query .wp-block-post-template .wp-block-post .wp-block-post-title > a'):
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
