import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered

class ChosunFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "朝鲜日报"
    allowed_domains = ["chosun.com"]
    start_urls = ["https://cnnews.chosun.com/client/news/lst.asp?cate=C01&mcate=M1003","https://cnnews.chosun.com/client/news/lst.asp?cate=C01&mcate=M1003&cpage=2"]

    def parse_detail(self, response):
        itm = response.meta['item']

        pub_time_str = response.xpath('//*[@id="Wrapper"]//div[@class="realcons"]/div[@class="date_text"]/p/text()').extract_first('')
        if pub_time_str:
            raw_time_str = pub_time_str.replace('&nbsp;', ' ').replace('输入 : ', '').replace('更新 : ', '')
            time_parts = raw_time_str.split('|')
            if len(time_parts) >= 2:
                pub_time_str = time_parts[1].strip()
                mod_time_str = time_parts[0].strip()
                print(pub_time_str, mod_time_str)
                pub_time = self.to_utc_string(self.name,pub_time_str)
                mod_time = self.to_utc_string(self.name,mod_time_str)
                itm['pub_time'] = pub_time
                itm['mod_time'] = mod_time
                if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                    self.logger.info(f'新闻过期：{pub_time}|{response.url}')
                    return

        clean_text = response.xpath('//*[@id="articleBody"]/text()')
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
        for itm in response.xpath('//*[@id="Wrapper"]//div[@class="consWrap"]/div[@class="articleList"]/ul/li'):
            url = response.urljoin(itm.xpath('./div[@class="txt"]/a/@href').extract_first(''))
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = itm.xpath('./div[@class="txt"]/a/strong/text()').extract_first('')
            pub_time = ''
            mod_time = ''
            desc = itm.xpath('./div[@class="txt"]/a/p/text()').extract_first('')
            lang = ''
            content = ''
            source = itm.xpath('./div[@class="txt"]/a//span[@class="name"]/text()').extract_first('')
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
