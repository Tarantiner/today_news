import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class AbcFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "澳大利亚广播公司"
    allowed_domains = ["www.abc.net.au"]

    # 动态生成start_requests
    async def start(self):
        yield scrapy.Request("https://www.abc.net.au/news/justin", callback=self.parse_pagination)

    def parse_pagination(self, response):
        document_id = response.xpath('//div[@data-component="PaginationList"]/@data-uri').extract_first('')
        if document_id:
            document_id = document_id.split('/')[-1]
            url = f"https://www.abc.net.au/news-web/api/loader/channelrefetch?name=PaginationArticlesFuture&documentId={document_id}&prepareParams={{%22imagePosition%22:{{%22mobile%22:%22right%22,%22tablet%22:%22right%22,%22desktop%22:%22right%22}}}}&future=true&offset=0&size=250&total=250"
            yield scrapy.Request(url, callback=self.parse)

    def parse_detail(self, response):
        itm = response.meta['item']

        clean_text = response.xpath('//main[@id="content"]//div[@data-component="ArticleWeb"]//div[contains(@class, "engagement_target")]').xpath('string(.)')
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

        source = response.xpath('//meta[@name="twitter:site"]/@content').extract_first('')
        if source:
            itm['source'] = source

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
        data = response.json()
        for itm in data.get('collection', []):
            url = response.urljoin(itm.get('link', ''))
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = itm.get('title', '')

            pub_time = self.to_utc_string(self.name,itm.get('dates', {}).get('firstPublished', ''))
            if not pub_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                continue

            mod_time = self.to_utc_string(self.name,itm.get('dates', {}).get('lastUpdated', ''))
            desc = ''
            lang = ''
            content = ''
            source = ''
            keywords = ''
            images = [
                {'url': itm.get('image', '').get('imgSrc', ''), 'caption': itm.get('image', '').get('altText', ''), 'img_time': ''}
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
