import scrapy
import json
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered

class SbsAuFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "澳大利亚特别节目广播事业局"
    allowed_domains = ["sbs.com.au"]
    start_urls = ["https://www.sbs.com.au/language/chinese/zh-hans/collection/mandarin-news?page=1"]
    has_expired_news = False

    def parse_detail(self, response):
        itm = response.meta['item']

        pub_time_str = response.xpath('//meta[@name="updated_date"]/@content').extract_first('')
        if pub_time_str:
            pub_time = self.to_utc_string(self.name,pub_time_str)
            itm['pub_time'] = pub_time
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{response.url}')
                self.has_expired_news = True
                return

        desc = response.xpath('//meta[@property="og:description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        clean_text = response.xpath('//*[@id="BPE-article-body"]/p[@class="bodyParagaph"]/span/text()')
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

        source = response.xpath('//meta[@property="og:site_name"]/@content').extract_first('')
        if source:
            itm['source'] = source

        if not itm.get('images'):
            img_list = response.xpath('//meta[@property="og:image"]')
            if img_list:
                img_url = img_list[0].xpath('./@content').extract_first('')
                img_caption = response.xpath('//meta[@property="og:image:alt"]/@content').extract_first('')
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
        for itm in response.xpath('//div[contains(@class, "SBS_ShelfItem")]'):
            url = response.urljoin(itm.xpath('.//a[@data-testid="headline"]/@href').extract_first(''))
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue

            # 尝试从 data-clickevent 属性中提取标题
            clickevent_data = itm.xpath('.//a[@data-testid="headline"]/@data-clickevent').extract_first('')
            title = ''
            if clickevent_data:
                try:
                    # 解析 JSON 字符串获取标题
                    event_data = json.loads(clickevent_data)
                    title = event_data.get('elementText', '')
                except (json.JSONDecodeError, ValueError):
                    # 如果解析失败，尝试从原来的位置获取
                    print(f'解析 data-clickevent 失败：{clickevent_data}')
            else:
                # 如果没有 data-clickevent 属性，从原来的位置获取
                print(f'没有 data-clickevent 属性')

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
        
        # 动态翻页，遇到过期新闻时停止
        if not self.has_expired_news:
            # 提取当前页码
            current_page = 1
            if 'page=' in response.url:
                current_page = int(response.url.split('page=')[-1])
            # 生成下一页请求
            next_page = current_page + 1
            next_url = f"https://www.sbs.com.au/language/chinese/zh-hans/collection/mandarin-news?page={next_page}"
            yield scrapy.Request(next_url, callback=self.parse)