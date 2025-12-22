import re
import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class ChinatimesSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "中時新聞網"
    allowed_domains = ["chinatimes.com"]
    start_urls = ["https://www.chinatimes.com/robots.txt"]

    def parse_detail(self, response):
        d1 = response.xpath('//div[@class="article-body"]')
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
        if not itm['content']:
            itm['content'] = 'content'

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        if not itm.get('images'):
            img_url = response.xpath('//div[@class="main-figure"]/figure/div/img/@src').extract_first('')
            if img_url:
                img_caption = response.xpath('//div[@class="main-figure"]/figure/div/img/@alt').extract_first('')
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

        mod_time = self.to_utc_string(response.xpath('//meta[@property="article:modified_time"]/@content').extract_first(''))
        if mod_time:
            itm['mod_time'] = mod_time

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse_url_list(self, response):
        response.selector.remove_namespaces()
        for itm in response.xpath('//url'):
            url = itm.xpath('./loc/text()').extract_first('')
            if not url:
                continue
            if self.match_invalid_url(url):
                continue
            title = itm.xpath('./news/title/text()').extract_first('')
            if not title:
                continue
            pub_time = self.to_utc_string(itm.xpath('./news/publication_date/text()').extract_first(''))
            if not pub_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                continue

            mod_time = ''
            desc = ''
            lang = itm.xpath('./news/publication/language/text()').extract_first('')
            content = ''
            source = itm.xpath('./news/publication/name/text()').extract_first('')
            keywords = itm.xpath('./news/keywords/text()').extract_first('')
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

    def parse(self, response):
        url_list = re.findall('https://www.chinatimes.com/sitemaps/sitemap_todaynews\w{0,3}.xml', response.text)
        if len(url_list) > 0:
            self.logger.info(f'找到{len(url_list)}个新闻列表url')
            for url in url_list:
                yield scrapy.Request(url, callback=self.parse_url_list)
        else:
            self.logger.warning(f'未找到新闻列表url')
