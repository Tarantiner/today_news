import re
import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class WorldjournalSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "世界新闻网"
    allowed_domains = ["worldjournal.com"]
    start_urls = ["https://www.worldjournal.com/sitemap/gnews"]

    # 统一utc时间字符串
    def parse_time(self, time_str):
        try:
            if not time_str:
                return ''
            # 直接解析带时区的时间
            dt = datetime.datetime.fromisoformat(time_str)  # Python 3.7+
            print(dt)  # 2025-11-09 16:46:27-05:00

            # 格式化为字符串
            formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
            # print(formatted)  # 2025-11-09 16:46:27

            # 转换为本地时间
            local_dt = dt.astimezone()
            # print(local_dt.strftime("%Y-%m-%d %H:%M:%S %Z"))  # 2025-11-10 05:46:27 CST

            # 转换为UTC时间
            utc_dt = dt.astimezone(datetime.timezone.utc)
            format_time = utc_dt.strftime("%Y-%m-%d %H:%M:%S")  # 2025-11-09 21:46:27 UTC
            print(f'{time_str}==>{format_time}')
            return format_time
        except Exception as e:
            self.logger.info(f'转换时间失败:{type(e)}|{time_str}')
            return ''

    def clean_txt(self, txt):
        return txt.strip().replace('![CDATA[', '').replace(']]', '').strip()

    def parse_detail(self, response):
        d1 = response.xpath('//section[@class="article-content__editor"]')
        clean_text = d1.xpath('.//p[not(ancestor::section[@class="next-page"])]').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p:
                # print([_p])
                txt_list.append(_p)
        itm = response.meta['item']
        # print('\n'.join(txt_list))
        itm['content'] = '\n'.join(txt_list)
        if not itm['content']:
            itm['content'] = 'content'

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        if not itm.get('images'):
            img_list = response.xpath(
                '//figure[@class="article-content__image"]/picture/img')
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
            itm['keywords'] = response.xpath('//section[@class="article-content__editor"]/figure/picture/img/@src').extract_first('')

        try:
            mod_time = self.parse_time(re.search('"dateModified": ?"(.*?)"', response.text).group(1))
            if mod_time:
                itm['mod_time'] = mod_time
        except:
            pass

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse_url_list(self, response):
        response.selector.remove_namespaces()
        for itm in response.xpath('//url'):
            url = itm.xpath('./loc/text()').extract_first('')
            if not url:
                continue
            if self.match_invalid_url(url):
                continue
            title = self.clean_txt(itm.xpath('./news/title/text()').extract_first(''))
            if not title:
                continue
            pub_time = self.parse_time(itm.xpath('./news/publication_date/text()').extract_first(''))
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

    def parse(self, response):
        if response.request.url == self.start_urls[0]:
            response.selector.remove_namespaces()
            url_list = response.xpath('//loc/text()').extract()
            if len(url_list) > 0:
                self.logger.info(f'找到{len(url_list)}个新闻列表url')
                for url in url_list:
                    yield scrapy.Request(url, callback=self.parse_url_list)
            else:
                self.logger.warning(f'未找到新闻列表url')
