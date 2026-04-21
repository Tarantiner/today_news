import scrapy
import datetime
from dateutil import parser as date_parser
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class JustTheNewsFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "只是新闻"
    allowed_domains = ["justthenews.com"]
    start_urls = ["https://justthenews.com/government"]

    # 统一utc时间字符串
    def parse_time(self, time_str):
        try:
            if not time_str:
                return ''
            # 去掉前缀 "Published: "（不区分大小写）
            clean_str = time_str.strip()
            if clean_str.lower().startswith("published:"):
                clean_str = clean_str[len("Published:"):].strip()

            # 解析时间为 datetime 对象
            local_dt = date_parser.parse(clean_str)

            # 为本地时区
            if local_dt.tzinfo is None:
                local_dt = local_dt.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)

            # 转换为 UTC 时间
            utc_dt = local_dt.astimezone(datetime.timezone.utc)

            # 格式化为 ISO 8601 UTC 字符串，带毫秒和 'Z'
            formatted = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
            return formatted
        except Exception as e:
            self.logger.info(f'转换时间失败:{type(e)}|{time_str}')
            return ''

    def parse_detail(self, response):
        itm = response.meta['item']
        
        title = response.css('.node__content .node__title h1::text').extract_first('')
        if title:
            itm['title'] = title.strip()

        pub_time = response.css('p[class="published__paragraph"]::text').extract_first('')
        if pub_time:
            itm['pub_time'] = self.parse_time(pub_time)

        itm['mod_time'] = ''

        clean_text = response.css('.node__content .node__main_content .node__text .text-long p::text')
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

        source = response.xpath('//meta[@property="og:site_name"]/@content').extract_first('')
        if source:
            itm['source'] = source

        if not itm.get('images'):
            img_list = response.xpath('//meta[@property="og:image:url"]')
            if img_list:
                img_url = response.urljoin(img_list[0].xpath('./@content').extract_first(''))
                img_caption = img_list[0].xpath('//meta[@property="og:image:alt"]/@content').extract_first('')
                img_time = ''
                images = [
                    {'url': img_url, 'caption': img_caption, 'img_time': img_time}
                ]
                images = images
            else:
                images = []
            itm['images'] = images

        itm['keywords'] = ''

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def match_invalid_url(self, url):
        if '/video/' in url or '/photo/' in url:
            return True
        return False

    def parse(self, response):
        if response.request.url == self.start_urls[0]:
            response.selector.remove_namespaces()
            for itm in response.css('.view-content article .node__text h3 a'):
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
