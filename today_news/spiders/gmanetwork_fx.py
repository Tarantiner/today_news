import scrapy
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered

class GmanetworkFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "GMA新闻网"
    allowed_domains = ["gmanetwork.com", "gmanews.tv"]

    def start_requests(self):
        # 主sitemap URL
        main_sitemap_url = 'https://data.gmanetwork.com/gno/widgets/grid_reverse_listing/story_news/tracker.gz'
        # 请求主sitemap
        yield scrapy.Request(main_sitemap_url, callback=self.parse_main_sitemap)

    def parse_main_sitemap(self, response):
        # 提取出count
        count = response.json().get('count', 0)
        if not count:
            return
        sitemap_link = f'https://data.gmanetwork.com/gno/widgets/grid_reverse_listing/story_news/{count}.gz'
        # 为子sitemap链接创建新的请求
        yield scrapy.Request(sitemap_link, callback=self.parse)

    def parse_detail(self, response):
        itm = response.meta['item']

        mod_time = response.xpath('//meta[@property="lastmod"]/@content').extract_first('')
        if mod_time:
            itm['mod_time'] = self.to_utc_string(self.name,mod_time)

        clean_text = response.xpath('//div[@class="story_main"]/p/text() | //div[@class="article-body"]/p/text()')
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

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        has_expired_news = False
        
        data_list = response.json().get('data', [])
        for itm in data_list:
            url = itm.get('article_url', '')
            if not url:
                continue
            # 处理相对路径
            if not url.startswith('http'):
                url = 'https://www.gmanetwork.com/news/' + url
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = itm.get('title', '')
            pub_time = self.to_utc_string(self.name,itm.get('publish_timestamp', ''))
            if not pub_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                has_expired_news = True
                continue
            mod_time = ''
            desc = itm.get('lead', '')
            lang = ''
            content = ''
            source = itm.get('author', '')
            keywords = itm.get('tags', '')
            images = [
                {
                    'url': itm.get('photo', {}).get('base_url', '') + itm.get('photo', {}).get('image_filename', ''), 
                    'caption': itm.get('photo', {}).get('photo_title', ''), 
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
            if 'story_news/' in response.url:
                current_page = int(response.url.split('story_news/')[-1].split('.gz')[0])
            # 生成下一页请求
            next_page = current_page - 1
            next_url = f"https://data.gmanetwork.com/gno/widgets/grid_reverse_listing/story_news/{next_page}.gz"
            yield scrapy.Request(next_url, callback=self.parse)

