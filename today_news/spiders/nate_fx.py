import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered

class NateFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "Nate新闻"
    allowed_domains = ["news.nate.com", "nateimg.co.kr"]
    start_urls = ["https://news.nate.com/recent?mid=n0501&page=1"]

    def parse_detail(self, response):
        itm = response.meta['item']

        clean_text = response.xpath('//*[@id="realArtcContents"]//text()')
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
            img_list = response.xpath('//meta[@property="og:image"]')
            if img_list:
                img_url = response.urljoin(img_list[0].xpath('./@content').extract_first(''))
                img_caption = ''
                img_time = ''
                images = [
                    {'url': img_url, 'caption': img_caption, 'img_time': img_time}
                ]
                images = images
            else:
                images = []
            itm['images'] = images

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
        
        for itm in response.xpath('//*[@id="newsContents"]//div[@class="postSubjectContent"]/div[@class="mduSubjectList"]'):
            url = response.urljoin(itm.xpath('.//a/@href').extract_first(''))
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = itm.xpath('.//a/span[@class="tb"]/h2/text()').extract_first('')
            # 01-15 15:24缺少年份，补充当前年份
            pub_time = self.to_utc_string(self.name,f"{datetime.datetime.now().year}-{itm.xpath('.//span[@class="medium"]/font/em/text()').extract_first('')}")
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
        
        # 动态翻页，遇到过期新闻时停止
        if not has_expired_news:
            # 提取当前页码
            current_page = 1
            if 'page=' in response.url:
                current_page = int(response.url.split('page=')[-1])
            # 生成下一页请求
            next_page = current_page + 1
            next_url = f"https://news.nate.com/recent?mid=n0501&page={next_page}"
            yield scrapy.Request(next_url, callback=self.parse)
