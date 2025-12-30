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

    def match_invalid_url(self, url):
        # 財經 {'121209', '121477', '121347', '121208'}
        # 美國 {'121618', '121469', '121172', '121177'}
        # 洛杉磯 {'121359', '122693', '121471', '121360', '121365'}
        # 觀點 {'121201', '121206'}
        # 川普2.0 {'124279', '121468', '121148', '124278', '124277'}
        # 中國 {'121474', '121343', '121341', '121344', '121339'}
        # 紐約 {'121382', '121470', '121381', '121390', '121388'}
        # 生活 {'121617', '121271', '121266', '121268'}
        # 國際 {'124211', '121257', '123308', '121488', '121261', '121480', '121256'}
        # 健康 {'121238', '121240', '121242', '122009'}
        # 藝文 {'121251', '121250', '121428', '121535', '121253', '124667', '121252', '122163'}
        # 台灣 {'121223', '121475', '121218', '121222', '121221', '121220'}
        # 運動 {'121226', '121225', '121229', '121517', '121227'}
        # 娛樂 {'121235', '121233', '121478', '121234', '121232'}
        # 消費 {'122986', '122985', '122981', '122984', '122982'}
        # 教育 {'122038'}
        # 舊金山 {'121368', '121375', '121374', '121369', '121519', '121472'}
        # 地方 {'121278', '121275', '121274', '121277', '121282', '121473'}
        # 汽車 {'121318'}
        # 周刊 {'124683'}
        if any((
                '/story/121617/' in url, '/story/121271/' in url, '/story/121266/' in url,
                '/story/121268/' in url, '/story/121238/' in url, '/story/121240/' in url,
                '/story/121242/' in url, '/story/122009/' in url,
                '/story/121251/' in url, '/story/121250/' in url, '/story/121428/' in url,
                '/story/121535/' in url, '/story/121253/' in url, '/story/124667/' in url,
                '/story/121252/' in url, '/story/122163/' in url,
                '/story/121226/' in url, '/story/121225/' in url, '/story/121229/' in url,
                '/story/121517/' in url, '/story/121227/' in url, '/story/121235/' in url,
                '/story/121233/' in url, '/story/121478/' in url, '/story/121234/' in url,
                '/story/121232/' in url, '/story/122986/' in url, '/story/122985/' in url,
                '/story/122981/' in url, '/story/122984/' in url, '/story/122982/' in url,
                '/story/122038/' in url, '/story/121318/' in url, '/story/124683/' in url,
        )):
            return True
        return False

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
            mod_time = self.to_utc_string(re.search('"dateModified": ?"(.*?)"', response.text).group(1))
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
            # try:
            #     cate = re.search('-- cate：(.*?) \|', itm.extract()).group(1)
            # except:
            #     pass
            url = itm.xpath('./loc/text()').extract_first('')
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = self.clean_txt(itm.xpath('./news/title/text()').extract_first(''))
            if not title:
                continue
            pub_time = self.to_utc_string(itm.xpath('./news/publication_date/text()').extract_first(''))
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
