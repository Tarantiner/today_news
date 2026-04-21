import scrapy
import datetime
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered

class YtnFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "YTN新闻"
    allowed_domains = ["ytn.co.kr"]

    def start_requests(self):
        url = "https://www.ytn.co.kr/ajax/getMoreNews.php"
        formdata = {
            'mcd': '0104',
            'page': '1'
        }
        yield scrapy.FormRequest(
            url=url,
            formdata=formdata,
            callback=self.parse
        )

    def parse_detail(self, response):
        itm = response.meta['item']

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def parse(self, response):
        import json
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse JSON response: {response}")
            return
        
        has_expired_news = False
        
        for news_item in data.get('data', []) if isinstance(data, dict) else data:
            # 根据实际响应结构提取字段
            url = response.urljoin('/_ln/0104_' + news_item.get('join_key', '') if isinstance(news_item, dict) else '')
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = news_item.get('title', '') if isinstance(news_item, dict) else ''
            pub_time_str = news_item.get('n_date', '') if isinstance(news_item, dict) else ''
            # 处理发布时间，根据实际格式调整
            if pub_time_str:
                # 示例：如果时间格式是 "2026.01.19. 07:33"
                if len(pub_time_str.split('.')) == 4 and len(pub_time_str.split(' ')) == 2:
                    pub_time = self.to_utc_string(self.name,f"{pub_time_str.split('.')[0]}-{pub_time_str.split('.')[1]}-{pub_time_str.split('.')[2]} {pub_time_str.split('.')[3]}")
                else:
                    pub_time = self.to_utc_string(self.name,pub_time_str)
            else:
                pub_time = ''
            
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
            content = news_item.get('content', '') if isinstance(news_item, dict) else ''
            source = ''
            keywords = ''
            images = [
                {'url': response.urljoin(news_item.get('img', '') if isinstance(news_item, dict) else ''), 'caption': '', 'img_time': ''}
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
            yield scrapy.Request(url, meta={'snapshot': True, 'item': itm, 'detail': True},
                                 callback=self.parse_detail, errback=self.parse_detail_failed)
        
        # 动态翻页，遇到过期新闻时停止
        if not has_expired_news:
            # 提取当前页码
            current_page = 1
            # 从请求参数中获取当前页码
            if 'page' in response.meta.get('formdata', {}):
                current_page = int(response.meta['formdata']['page'])
            # 生成下一页请求
            next_page = current_page + 1
            next_url = "https://www.ytn.co.kr/ajax/getMoreNews.php"
            formdata = {
                'mcd': '0104',
                'page': str(next_page)
            }
            yield scrapy.FormRequest(
                url=next_url,
                formdata=formdata,
                callback=self.parse,
                meta={'formdata': formdata}
            )
