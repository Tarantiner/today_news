import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class MsFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "MSNBC"
    allowed_domains = ["www.ms.now","res.cloudinary.com"]
    start_urls = ["https://www.ms.now/top-stories"]

    def parse_detail(self, response):
        itm = response.meta['item']
        
        title = response.css('.wp-block-group.alignfull.opinion-header .wp-block-group.title-and-dek-column h1::text').extract_first('')
        if title:
            itm['title'] = title
        else:
            title = response.css('.wp-block-columns.alignwide.is-layout-flex .wp-block-column.is-layout-flow h1::text').extract_first('')
            if title:
                itm['title'] = title

        pub_time = response.xpath('//meta[@property="article:published_time"]/@content').extract_first('')
        if pub_time:
            itm['pub_time'] = self.to_utc_string(self.name,pub_time)

        mod_time = response.xpath('//meta[@property="article:modified_time"]/@content').extract_first('')
        if mod_time:
            itm['mod_time'] = self.to_utc_string(self.name,mod_time)

        clean_text = response.css('.wp-block-group.alignfull.article-content .entry-content.alignfull.ends-with-logo.wp-block-post-content p::text')
        if not clean_text:
            clean_text = response.css('.wp-block-group.alignfull .entry-content.alignfull.ends-with-logo.wp-block-post-content p::text')
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

        source = response.xpath('//meta[@name="author"]/@content').extract_first('')
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
            keywords = response.xpath('//meta[contains(@name,"twitter:label")]/@content').extract()
            itm['keywords'] = ','.join(keywords)

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
            for itm in response.css('.is-layout-constrained.wp-block-group-is-layout-constrained .alignfull .has-article-separator > a'):
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
