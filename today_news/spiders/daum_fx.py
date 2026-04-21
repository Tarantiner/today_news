import re
import scrapy
import demjson3
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class DaumFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "Daum新闻"
    allowed_domains = ["daum.net", "daumcdn.net", "kakaocdn.net"]
    start_urls = ["https://news.daum.net/global"]

    def parse_detail(self, response):
        itm = response.meta['item']

        clean_text = response.xpath('//*[@id="mArticle"]//div[@class="article_view"]//p')
        txt_list = []
        for p in clean_text.extract():
            # 去除HTML标签
            _p = remove_tags(p)
            _p = self.clean_phrase(_p)
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
        # 1. 提取整个 data 数组
        script_text = response.xpath('//script[contains(., "const data")]/text()').get()
        if not script_text:
            self.logger.error("未找到数据脚本")
            return
        
        match = re.search(r'const data = (\[.*?\]);', script_text, re.DOTALL)
        if not match:
            self.logger.error("无法提取data数组")
            return
        
        try:
            data_array = demjson3.decode(match.group(1))
            
            # 2. 动态查找所有contents数组
            news_list = self._find_contents_recursive(data_array)
            
            if not news_list:
                self.logger.error("未找到任何contents数据")
                return
                
        except Exception as e:
            self.logger.error(f"JSON解析失败: {e}")
            return
        
        self.logger.info(f"成功提取 {len(news_list)} 条新闻")
    
        if not news_list:
            return
        # 提取moUrl字段
        for itm in news_list:
            url = itm.get('moUrl', '')
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = itm.get('title', '')
            pub_time = self.to_utc_string(self.name,itm.get('createdAt', ''))
            if not pub_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
                continue

            mod_time = ''
            desc = itm.get('summary', '')
            lang = ''
            content = ''
            source = itm.get('cpName', '')
            keywords = ''
            images = [
                {
                    'url': itm.get('cpImage', ''),
                    'caption': '',
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
    
    def _find_contents_recursive(self, data):
        """递归查找所有包含新闻的contents数组"""
        if isinstance(data, dict):
            # 检查当前字典是否包含新闻contents
            if 'contents' in data and isinstance(data['contents'], list):
                # 验证是新闻数据（包含title等字段）
                if (len(data['contents']) > 0 and 
                    isinstance(data['contents'][0], dict) and 
                    'title' in data['contents'][0]):
                    return data['contents']
            
            # 递归查找所有值
            for value in data.values():
                result = self._find_contents_recursive(value)
                if result:
                    return result
                    
        elif isinstance(data, list):
            # 遍历列表中的每个元素
            for item in data:
                result = self._find_contents_recursive(item)
                if result:
                    return result
        
        return None