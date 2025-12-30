import re
import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class IndependentSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "独立报"
    allowed_domains = ["independent.co.uk"]
    start_urls = ["https://www.independent.co.uk/sitemaps/googlenews"]

    def parse_detail(self, response):
        d1 = response.xpath('//div[@id="main"]')
        try:
            clean_text = d1.xpath('.//ul')[0].xpath('.//li').xpath('string(.)')
        except:
            clean_text = d1.xpath('./p').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p:
                print([_p])
                txt_list.append(_p)
        itm = response.meta['item']
        # print('\n'.join(txt_list))
        itm['content'] = '\n'.join(txt_list)
        if not itm['content']:
            itm['content'] = 'content'

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        if not itm.get('keywords'):
            try:
                itm['keywords'] = ','.join(eval(response.xpath('//meta[@property="keywords"]/@content').extract_first('')))
            except:
                pass

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    # def match_invalid_url(self, url):
    #     # ['extras', 'news', 'deals', 'life-style', 'us', 'home-improvement', 'sport', 'f1', 'asia', 'travel', 'tech',
    #     # 'arts-entertainment', 'games', 'voices', 'money', 'cars', 'health-and-fitness', 'bulletin']
    #     try:
    #         cate = re.search('independent.co.uk/(\S+?)/', url).group(1)
    #         if cate in ['news', 'us', 'asia', 'bulletin']:
    #             if cate == 'news' and any(['uk/news/health' in url, 'uk/news/business' in url, 'uk/news/science' in url]):
    #                 # ['health', 'world', 'science', 'business', 'uk']
    #                 return True
    #             return False
    #         return True
    #     except:
    #         return False

    def parse(self, response):
        if response.request.url == self.start_urls[0]:
            response.selector.remove_namespaces()
            for itm in response.xpath('//url'):
                url = itm.xpath('./loc/text()').extract_first('')
                if not url:
                    continue
                if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
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

                mod_time = self.to_utc_string(itm.xpath('./lastmod/text()').extract_first(''))
                desc = ''
                lang = itm.xpath('./news/publication/language/text()').extract_first('')
                content = ''
                source = itm.xpath('./news/publication/name/text()').extract_first('')
                keywords = itm.xpath('./news/keywords/text()').extract_first('')

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
                                     callback=self.parse_detail, errback=self.parse_detail_failed)
