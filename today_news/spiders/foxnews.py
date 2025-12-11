import re
import json
import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class ApnewsSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "福克斯新闻网"
    allowed_domains = ["foxnews.com"]
    start_urls = ["https://www.foxnews.com/sitemap.xml?type=news"]

    # 统一utc时间字符串
    def parse_time(self, time_str):
        try:
            if not time_str:
                return ''
            # 直接解析带时区的时间
            dt = datetime.datetime.fromisoformat(time_str)  # Python 3.7+
            print(dt)  # 2025-11-09 16:46:27-05:00

            # 格式化为字符串
            formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
            # print(formatted)  # 2025-11-09 16:46:27

            # 转换为本地时间
            local_dt = dt.astimezone()
            # print(local_dt.strftime("%Y-%m-%d %H:%M:%S %Z"))  # 2025-11-10 05:46:27 CST

            # 转换为UTC时间
            utc_dt = dt.astimezone(datetime.timezone.utc)
            format_time = utc_dt.strftime("%Y-%m-%d %H:%M:%S")  # 2025-11-09 21:46:27 UTC
            print(f'{time_str}==>{format_time}')
            return format_time
        except Exception as e:
            self.logger.info(f'转换时间失败:{type(e)}|{time_str}')
            return ''

    def match_invalid_url(self, url):
        # ['us', 'deals', 'politics', 'food-drink', 'health', 'tech', 'sports', 'opinion', 'world', 'lifestyle', 'entertainment', 'media', 'travel']
        try:
            cate = re.search('foxnews.com/(\S+?)/', url).group(1)
            if cate in ['deals', 'food-drink', 'health', 'sports', 'lifestyle', 'article', 'entertainment', 'travel']:
                return True
            return False
        except:
            return False

    def parse_detail(self, response):
        # d1 = response.xpath('//div[@class="article-body"]')
        # clean_text = d1.xpath('.//p[not(ancestor::div[@class="Infobox"])]').xpath('string(.)')
        # txt_list = []
        # for p in clean_text.extract():
        #     _p = self.clean_phrase(p)
        #     if _p:
        #         # print([_p])
        #         txt_list.append(_p)
        # itm = response.meta['item']
        # # print('\n'.join(txt_list))
        # itm['content'] = '\n'.join(txt_list)
        # if not itm['content']:
        #     itm['content'] = 'content'

        itm = response.meta['item']
        try:
            content = [i for i in json.loads(response.xpath('//script[@type="application/ld+json"]/text()').extract_first())['@graph'] if i['@type']=='NewsArticle'][0]['articleBody']
            itm['content'] = content.replace('. ', '.\n').replace('  ', '\n')
        except:
            itm['content'] = ''
        if not itm['content']:
            itm['content'] = 'content'

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        if not itm.get('images'):
            img_url = response.xpath('//meta[@property="og:image"]/@content').extract_first('')
            if img_url:
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
            try:
                itm['keywords'] = ','.join(json.loads(re.search('keywords": ?(\[.*?\])', response.text).group(1)))
            except:
                pass

        mod_time = self.parse_time(response.xpath('//meta[@name="dcterms.modified"]/@content').extract_first(''))
        if mod_time:
            itm['mod_time'] = mod_time

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
            for itm in response.xpath('//url'):
                url = itm.xpath('./loc/text()').extract_first('')
                if not url:
                    continue
                if self.match_invalid_url(url):
                    continue
                title = itm.xpath('./news/title/text()').extract_first('')
                if not title:
                    continue
                pub_time = self.parse_time(itm.xpath('./news/publication_date/text()').extract_first(''))
                if not pub_time:
                    continue
                # 检查过期资讯并过滤
                if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get(
                        'NEWS_EXPIRE_DAYS')):
                    self.logger.info(f'新闻过期：{pub_time}|{url}')
                    continue

                mod_time = ''
                desc = ''
                lang = itm.xpath('./news/publication/language/text()').extract_first('')
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
