import scrapy
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered

class CfrFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "外交关系委员会"
    allowed_domains = ["cfr.org"]
    start_urls = ["https://www.cfr.org/regions/asia/china/1"]

    def parse_detail(self, response):
        itm = response.meta['item']

        clean_text = response.xpath('//*[@id="page-content"]//p[contains(@class,"rich-text")]/span/text()')
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

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        response.selector.remove_namespaces()
        has_expired_news = False
        
        for itm in response.xpath('//*[@id="content"]//section//ul'):
            url = response.urljoin(itm.xpath('./li/article//h3/a/@href').extract_first(''))
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = itm.xpath('./li/article//h3/a/text()').extract_first('')
            pub_time = self.to_utc_string(self.name,itm.xpath('./li/article//div/time/@datetime').extract_first(''))
            if not pub_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                has_expired_news = True
                continue
            mod_time = ''
            desc = ''
            lang = ''
            content = ''
            source = ''
            keywords = ''
            images = [
                {
                    'url': response.urljoin(itm.xpath('./li/article//img/@data-src').extract_first('')),
                    'caption': '',
                    'img_time': ''
                }
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
        
        # 动态翻页，遇到过期新闻时停止
        if not has_expired_news:
            # 提取当前页码
            current_page = 1
            if 'page=' in response.url:
                current_page = int(response.url.split('page=')[-1])
            # 生成下一页请求
            next_page = current_page + 1
            next_url = f"https://www.cfr.org/regions/asia/china/{next_page}"
            yield scrapy.Request(next_url, callback=self.parse)
