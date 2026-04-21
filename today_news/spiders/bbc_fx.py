import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered

class BbcFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "BBC"
    allowed_domains = ["www.bbc.com","ichef.bbci.co.uk"]
    
    def start_requests(self):
        # 主sitemap URL
        main_sitemap_url = 'https://www.bbc.com/sitemaps/https-index-com-news.xml'
        # 请求主sitemap
        yield scrapy.Request(main_sitemap_url, callback=self.parse_main_sitemap)

    def parse_main_sitemap(self, response):
        # 移除XML命名空间以便于XPath解析
        response.selector.remove_namespaces()
        # 使用XPath提取所有子sitemap链接
        sitemap_links = response.xpath('//sitemap/loc/text()').extract()
        # 为每个子sitemap链接创建新的请求
        for link in sitemap_links:
            yield scrapy.Request(link, callback=self.parse)

    def parse_detail(self, response):
        itm = response.meta['item']

        title = response.xpath('//*[@id="content"]/text()').extract_first('')
        if title:
            itm['title'] = title

        mod_time = response.xpath('//meta[@name="article:modified_time"]/@content').extract_first('')
        if mod_time:
            itm['mod_time'] = self.to_utc_string(self.name,mod_time)

        clean_text = response.xpath('//*[@id="main-wrapper"]/div/div/div/div[1]/main/div/p/text()')
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

        if not itm.get('images'):
            img_list = response.xpath('//meta[@property="og:image"]')
            if img_list:
                img_url = img_list[0].xpath('./@content').extract_first('')
                img_caption = img_list[0].xpath('//meta[@property="og:image:alt"]/@content').extract_first('')
                img_time = ''
                images = [
                    {'url': img_url, 'caption': img_caption, 'img_time': img_time}
                ]
                images = images
            else:
                images = []
            itm['images'] = images

        if not itm.get('keywords'):
            keywords = response.xpath('//meta[@name="article:tag"]/@content').extract()
            itm['keywords'] = ','.join(keywords)

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        response.selector.remove_namespaces()
        for itm in response.xpath('//url'):
            url = response.urljoin(itm.xpath('./loc/text()').extract_first(''))
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = ''

            pub_time = self.to_utc_string(self.name,itm.xpath('./news/publication_date/text()').extract_first(''))
            if not pub_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                continue

            mod_time = ''
            desc = ''
            lang = itm.xpath('./news/publication/language/text()').extract_first('')
            if lang != 'zh-cn':
                continue
            content = ''
            source = itm.xpath('./news/publication/name/text()').extract_first('')
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
