import re
import scrapy
import demjson3
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class NyTimesSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "纽约时报"
    allowed_domains = ["nytimes.com", "nyt.com"]
    start_urls = ["https://www.nytimes.com/sitemaps/new/news.xml.gz"]

    def match_invalid_url(self, url):
        # ['athletic', 'interactive', 'live', 'article', '2025', 'es', 'newsgraphics']
        # try:
        #     cate = re.search('nytimes.com/(\S+?)/', url).group(1)
        #     if cate in ['athletic', 'interactive', 'live', 'es', 'newsgraphics', 'article']:
        #         return True
        #     return False
        # except:
        #     return False
        try:
            if re.match('^https://www.nytimes.com/\d+/\d+/\d+/world/\S+$', url):
                return False
            return True
        except:
            return False

    def parse_detail(self, response):
        # d1 = response.xpath('//section[@name="articleBody"]')
        # clean_text = d1.xpath('./div[contains(@class, "StoryBodyCompanionColumn")]//p').xpath('string(.)')
        # txt_list = []
        # for p in clean_text.extract():
        #     _p = self.clean_phrase(p)
        #     if _p:
        #         print([_p])
        #         txt_list.append(_p)
        # itm = response.meta['item']
        # # print('\n'.join(txt_list))
        # itm['content'] = '\n'.join(txt_list)
        # if not itm['content']:
        #     itm['content'] = 'content'

        itm = response.meta['item']
        try:
            txt_list = []
            s = re.search('<script>window.__preloadedData = (.*?);</script>', response.text).group(1)
            data = demjson3.decode(s)
            itm_list = data['initialData']['data']['article']['sprinkledBody']['content']
            for _itm in itm_list:
                if _itm.get('__typename') == 'ParagraphBlock':
                    content_list = _itm.get('content') or []
                    p_txt_list = []
                    for content in content_list:
                        if content.get('__typename') == 'TextInline':
                            txt = content['text']
                            if txt:
                                p_txt_list.append(txt)
                            # _p = self.clean_phrase(txt)
                            # if _p:
                            #     print([_p])
                            #     txt_list.append(_p)
                    txt_list.append(''.join(p_txt_list))
            itm['content'] = '\n'.join(txt_list)
            if not itm['content']:
                itm['content'] = 'content'
            # desc = data['initialData']['data']['article']['summary']
        except:
            self.logger.warning(f'提取{response.url}内容失败')
            itm['content'] = 'content'

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        if not itm.get('images'):
            img_list = response.xpath('//figure[@aria-label="media"]//picture/img')
            if img_list:
                img_url = img_list[0].xpath('./@src').extract_first('')
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
            itm['keywords'] = response.xpath('//meta[@name="news_keywords"]/@content').extract_first('')

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

