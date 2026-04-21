import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class ParstodayFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "今日帕尔斯"
    allowed_domains = ["parstoday.ir"]
    start_urls = ["https://parstoday.ir/zh/rss--mu__world"]

    def parse_detail(self, response):
        itm = response.meta['item']

        clean_text = response.xpath('//*[@id="item"]//div[@class="item-text"]/p[not(@class)]/text()')
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

        if not itm.get('source'):
            itm['source'] = response.xpath('//meta[@property="og:article:author"]/@content').extract_first('')

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
        response.selector.remove_namespaces()
        for itm in response.xpath('//item'):
            url = response.urljoin(itm.xpath('./link/text()').extract_first(''))
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = itm.xpath('./title/text()').extract_first('')
            if title:
                title = title
            pub_time = self.to_utc_string(self.name,itm.xpath('./pubDate/text()').extract_first(''))
            if not pub_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                continue

            mod_time = ''
            desc = itm.xpath('./description/text()').extract_first('')
            lang = ''
            content = ''
            source = ''
            keywords = ''
            images = [
                {'url': itm.xpath('./image/text()').extract_first(''), 'caption': '', 'img_time': ''}
            ]

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