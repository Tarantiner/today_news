import re
import json
import scrapy
import datetime
import traceback
from urllib import parse
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class RTHKSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "香港电台"
    # allowed_domains = ["news.rthk.hk"]
    start_urls = [
        'https://news.rthk.hk/rthk/webpageCache/services/loadModNewsShowSp2List.php?lang=zh-TW&cat=4&newsCount=60&dayShiftMode=1&archive_date=',
    ]

    def parse_detail(self, response):
        itm = response.meta['item']
        d1 = response.xpath('//div[@class="itemFullText"]')
        txt_list = []
        for p in d1.xpath('./text()').extract():
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
                img_url = img_list[0].xpath('./@content').extract_first('')
                img_caption = img_list[0].xpath('./@alt').extract_first('')
                img_time = ''
                images = [
                    {'url': img_url, 'caption': img_caption, 'img_time': img_time}
                ]
                images = images
            else:
                images = []
            itm['images'] = images

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        yield itm

    def parse_detail_failed(self, failure):
        return
        # if failure.check(DupeFiltered):
        #     return
        # else:
        #     yield failure.request.meta['item']

    def _parse_hkt_time(self, time_str):
        """解析HKT格式的时间字符串"""
        if not time_str:
            return ''
        
        time_str = time_str.strip()
        try:
            # 处理格式：2026-02-27 HKT 08:53
            parts = time_str.split()
            if len(parts) >= 3 and parts[1] == 'HKT':
                date_part = parts[0]
                time_part = parts[2]
                # 添加秒数
                if len(time_part.split(':')) == 2:
                    time_part += ':00'
                # 组合成标准格式
                standard_format = f"{date_part} {time_part} +0800"
                # 解析为datetime对象
                from datetime import datetime, timezone, timedelta
                dt = datetime.strptime(standard_format, '%Y-%m-%d %H:%M:%S %z')
                # 转换为UTC
                utc_dt = dt.astimezone(timezone.utc)
                # 格式化为字符串
                return utc_dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            print(f'解析HKT时间失败：{time_str}，错误：{e}')
        
        # 如果解析失败，尝试使用父类方法
        return self.to_utc_string(time_str)

    def parse(self, response):
        for itm in response.xpath('//div[@class="ns2-page"]//div[@class="ns2-inner"]'):
            url = itm.xpath('.//h4[@class="ns2-title"]/a/@href').extract_first('')
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = self.clean_phrase(
                itm.xpath('.//h4[@class="ns2-title"]/a/text()').extract_first(''))
            if not title:
                continue
            pub_time = self._parse_hkt_time(itm.xpath('.//div[@class="ns2-created"]/text()').extract_first(''))
            if not pub_time:
                continue
            # 检查过期资讯并过滤
            if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                self.logger.info(f'新闻过期：{pub_time}|{url}')
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
