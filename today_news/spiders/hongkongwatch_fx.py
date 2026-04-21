import scrapy
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class HongkongWatchFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "香港监察网"
    allowed_domains = ["hongkongwatch.org","squarespace-cdn.com"]
    start_urls = ["https://www.hongkongwatch.org/latest-news"]

    def parse_detail(self, response):
        itm = response.meta['item']
        
        title = response.xpath('//meta[@property="og:title"]/@content').extract_first('')
        if title:
            itm['title'] = title

        pub_time_str = response.xpath('//meta[@itemprop="datePublished"]/@content').extract_first('')
        if pub_time_str:
            pub_time = self.to_utc_string(self.name,pub_time_str)
            itm['pub_time'] = pub_time
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{response.url}')
                return

        mod_time_str = response.xpath('//meta[@itemprop="dateModified"]/@content').extract_first('')
        if mod_time_str:
            mod_time = self.to_utc_string(self.name,mod_time_str)
            itm['mod_time'] = mod_time

        clean_text = response.xpath('//article//div[contains(@id, "block")]//div[@class="sqs-html-content"]/p/text()')
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

        itm['desc'] = response.xpath('//meta[@itemprop="description"]/@content').extract_first('')

        source = response.xpath('//meta[@itemprop="author"]/@content').extract_first('')
        if source:
            itm['source'] = source

        if not itm.get('images'):
            img_list = response.xpath('//link[@type="image/x-icon"]')
            if img_list:
                img_url = response.urljoin(img_list[0].xpath('./@href').extract_first(''))
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
            for itm in response.xpath('//div[@class="summary-title"]/a'):
                url = response.urljoin(itm.xpath('./@href').extract_first(''))
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
