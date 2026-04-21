import scrapy
import datetime, pytz
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class NourNewsFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "伊朗努尔新闻网"
    allowed_domains = ["nournews.ir"]
    start_urls = ["https://nournews.ir/zh/Service/international","https://nournews.ir/zh/Service/international/Page-2","https://nournews.ir/zh/Service/international/Page-3"]

    # 统一utc时间字符串
    def parse_time(self, time_str):
        try:
            if not time_str:
                return ''

            # 1. 先尝试 ISO 格式
            try:
                dt = datetime.datetime.fromisoformat(time_str)
            except ValueError:
                # 2. 再尝试美式格式 12/9/2025 3:00:25 AM
                dt = datetime.datetime.strptime(time_str, '%m/%d/%Y %I:%M:%S %p')
                # 3. 美国东部时间
                tz = pytz.timezone('US/Eastern')
                dt = tz.localize(dt)        # 把 naive 时间变成 aware 时间

            # 以下沿用你原来的逻辑
            utc_dt = dt.astimezone(datetime.timezone.utc)
            return utc_dt.strftime('%Y-%m-%d %H:%M:%S')

        except Exception as e:
            self.logger.info(f'转换时间失败:{type(e)}|{time_str}')
            return ''

    def parse_detail(self, response):
        itm = response.meta['item']
        
        title = response.css('.news-item h1 span#Body_Body_lblNewsTitle::text').extract_first('')
        if title:
            itm['title'] = title

        pub_time_str = response.xpath('//meta[@itemprop="datePublished"]/@content').extract_first('')
        if pub_time_str:
            pub_time = self.parse_time(pub_time_str)
            itm['pub_time'] = pub_time
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{response.url}')
                return

        mod_time = response.xpath('//meta[@itemprop="dateModified"]/@content').extract_first('')
        if mod_time:
            itm['mod_time'] = self.parse_time(mod_time)

        clean_text = response.css('.news-item .body #Body_Body_lblNewsBody p::text')
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

        source = response.xpath('//meta[@itemprop="author"]/@content').extract_first('')
        if source:
            itm['source'] = source

        if not itm.get('images'):
            img_list = response.xpath('//meta[@property="og:image"]')
            if img_list:
                img_url = img_list[0].xpath('./@content').extract_first('')
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
            itm['keywords'] = response.xpath('//meta[@name="keywords"]/@content').extract_first('')

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
            for itm in response.css('.news-list #Body_Body_lblResult .news-item a'):
                url = response.urljoin(itm.css('::attr(href)').extract_first('')).replace('/Service', '')
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
