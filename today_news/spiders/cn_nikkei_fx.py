import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered

class CnNikkeiFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "日经中文网"
    allowed_domains = ["nikkei.com"]

    def start_requests(self):
        # 主sitemap URL
        main_sitemap_url = 'https://cn.nikkei.com/'
        # 请求主sitemap
        yield scrapy.Request(main_sitemap_url, callback=self.parse_main_sitemap)

    def parse_main_sitemap(self, response):
        # 提取所有子sitemap链接
        sitemap_links = response.xpath('//ul[@id="bannerList"]/li[contains(@class,"bannerCho")]//ul/li/a/@href').extract()
        # 为每个子sitemap链接创建新的请求
        for link in sitemap_links:
            # 使用response.urljoin处理相对路径
            full_url = response.urljoin(link)
            yield scrapy.Request(full_url, callback=self.parse)

    def parse_detail(self, response):
        itm = response.meta['item']

        clean_text = response.xpath('//div[@id="contentDiv"]/div[contains(@class,"newsText")]/p/text()')
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

        desc = response.xpath('//meta[@name="twitter:description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        source = response.xpath('//meta[@name="author"]/@content').extract_first('')
        if source:
            itm['source'] = source

        if not itm.get('images'):
            img_list = response.xpath('//meta[@name="twitter:image:src"]')
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
        
        for itm in response.xpath('//div[@class="newsDetailContent"]//dl/dt'):
            url = response.urljoin(itm.xpath('./a/@href').extract_first(''))
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = itm.xpath('./a/text()').extract_first('')
            pub_time = self.to_utc_string(self.name,itm.xpath('./span/text()').extract_first('').replace('(', '').replace(')', '').replace('/', '-') +' 00:00:00')
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
            if 'start=' in response.url:
                current_page = int(response.url.split('start=')[-1])
            # 生成下一页请求
            next_page = current_page + 1
            # 使用当前响应的URL作为基础，而不是最后一个新闻的URL
            if 'start=' in response.url:
                next_url = response.url.replace(f'start={current_page}', f'start={next_page}')
            else:
                next_url = f"{response.url}?start={next_page}"
            yield scrapy.Request(next_url, callback=self.parse)
