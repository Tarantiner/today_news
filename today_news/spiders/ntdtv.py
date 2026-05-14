import re
import gzip
import scrapy
import datetime
from scrapy.http import HtmlResponse
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class NtdtvSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "新唐人亚太台"
    # allowed_domains = ["ntdtv.com"]
    start_urls = ["https://www.ntdtv.com/assets/uploads/sitemap/sitemap_news_gb.xml.gz"]

    def parse_detail(self, response):
        itm = response.meta['item']
        title = response.xpath('//div[@class="article_title"]/h1/text()').extract_first('').strip('')
        if title:
            itm['title'] = title
        else:
            return

        d1 = response.xpath('//div[@itemprop="articleBody"]')
        clean_text = d1.xpath('./p').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p:
                print([_p])
                txt_list.append(_p)
        # print('\n'.join(txt_list))
        itm['content'] = '\n'.join(txt_list)
        if not itm['content']:
            itm['content'] = 'content'

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        if not itm.get('images'):
            img_list = response.xpath('//div[@class="featured_image"]/figure//img')
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

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        decompressed_data = gzip.decompress(response.body)
        text = decompressed_data.decode('utf-8')

        response = HtmlResponse(
            url=response.url,
            body=text.encode('utf-8'),
            encoding='utf-8',
            request=response.request
        )
        response.selector.remove_namespaces()

        for itm in response.xpath('//url'):
            url = itm.xpath('./loc/text()').extract_first('')
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue

            s = itm.extract()
            try:
                title = re.search(r'<news:title>(.*?)</news:title>', s).group(1)
                if not title:
                    continue
                pub_time = re.search(r'<news:publication_date>(.*?)</news:publication_date>', s).group(1)
                pub_time = self.to_utc_string(self.name, pub_time)
                if not pub_time:
                    continue
                # 检查过期资讯并过滤
                if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                    self.logger.info(f'新闻过期：{pub_time}|{url}')
                    continue
            except:
                continue

            mod_time = ''
            desc = ''
            try:
                lang = re.search(r'<news:language>(.*?)</news:language>', s).group(1)
            except:
                lang = ''
            content = ''
            try:
                source = re.search(r'<news:name>(.*?)</news:name>', s).group(1)
            except:
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
