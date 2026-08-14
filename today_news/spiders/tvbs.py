import re
import scrapy
import json
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class TvbsSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "TVBS新闻网"
    allowed_domains = ["tvbs.com.tw"]
    start_urls = [
        "https://news.tvbs.com.tw/crontab/sitemap/google",
        "https://news.tvbs.com.tw/crontab/sitemap/latest",
    ]

    def clean_txt(self, txt):
        return txt.strip().replace('![CDATA[', '').replace(']]', '').strip()

    def parse_detail(self, response):
        # d1 = response.xpath('//div[@class="article_content"]')
        # xpath_conditions = [
        #     'not(ancestor::div[@class="guangxuan"])',
        #     'not(ancestor::div[@class="widely_declared"])',
        #     'not(ancestor::span[@class="endtext"])',
        # ]

        # final_xpath = './/text()[' + ' and '.join(xpath_conditions) + ']'
        # clean_text = d1.xpath(final_xpath)
        # txt_list = []
        # for p in clean_text.extract():
        #     _p = self.clean_phrase(p)
        #     if _p:
        #         # print([_p])
        #         txt_list.append(_p)
        # itm = response.meta['item']
        # itm['content'] = '\n'.join(txt_list)
        # if not itm['content']:
        #     itm['content'] = 'content'

        itm = response.meta['item']
        try:
            data = json.loads(response.xpath('//script[@type="application/ld+json"]/text()').extract_first())
            content = data['articleBody']
            itm['content'] = re.sub('(參考資料：.*$)', '', content, flags=re.S)
            # itm['content'] = data['articleBody']
            # content_lis = [i for i in data if i['@type']=='NewsArticle']
            # if content_lis:
            #     content = content_lis[0]['articleBody']
            # else:
            #     content = ''
            # if not content:
            #     content_itm_list = sorted([j for i in data if i['@type']=='LiveBlogPosting' for j in i['liveBlogUpdate']], key=lambda x: x['datePublished'])
            #     content_list = []
            #     for content_itm in content_itm_list:
            #         _time = content_itm['datePublished']
            #         _content = content_itm['articleBody'].rstrip('\n')
            #         if not _content:
            #             continue
            #         content_list.append(f'{_time}:\n{_content}\n' if {_time} else f'{_content}\n')
            #     content = '\n'.join(content_list)
            # itm['content'] = content
        except:
            itm['content'] = ''
        if not itm['content']:
            itm['content'] = 'content'

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        if not itm.get('images'):
            img_list = response.xpath(
                '//div[@class="img_box"]/div[@class="img"]/img')
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
            itm['keywords'] = response.xpath('//meta[@name="keywords"]/@content').extract_first('')

        mod_time = self.to_utc_string(self.name, response.xpath('//meta[@property="article:modified_time"]/@content').extract_first(''))
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
        response.selector.remove_namespaces()
        for itm in response.xpath('//url'):
            url = itm.xpath('./loc/text()').extract_first('')
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = self.clean_txt(itm.xpath('./news/title/text()').extract_first(''))
            if not title:
                continue
            pub_time = self.to_utc_string(self.name, itm.xpath('./news/publication_date/text()').extract_first(''))
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
            keywords = self.clean_txt(itm.xpath('./news/keywords/text()').extract_first(''))
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
