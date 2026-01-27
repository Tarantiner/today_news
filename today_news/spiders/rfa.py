import re
import json
import scrapy
import datetime
import traceback
from urllib import parse
from datetime import datetime, date, timedelta
import calendar
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


class RfaSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "自由亚洲电台"

    @staticmethod
    def get_month_ranges():
        today = date.today()
        current_year = today.year
        current_month = today.month
        
        # 获取本月信息
        current_month_days = calendar.monthrange(current_year, current_month)[1]
        current_month_start = f"{current_year}-{current_month:02d}-01"
        current_month_end = f"{current_year}-{current_month:02d}-{current_month_days:02d}"
        
        # 获取上月信息
        if current_month == 1:
            last_month_year = current_year - 1
            last_month = 12
        else:
            last_month_year = current_year
            last_month = current_month - 1
        
        last_month_days = calendar.monthrange(last_month_year, last_month)[1]
        last_month_start = f"{last_month_year}-{last_month:02d}-01"
        last_month_end = f"{last_month_year}-{last_month:02d}-{last_month_days:02d}"
        
        # 返回 [上月范围, 本月范围]
        return [
            f"{last_month_start}+TO+{last_month_end}",
            f"{current_month_start}+TO+{current_month_end}"
        ]

    async def start(self):
        date_range = self.get_month_ranges()
        url = 'https://www.rfa.org/pf/api/v3/content/fetch/story_archive_story_feed_section'
        for date_range_item in date_range:
            params = {
                'query': f'{{"feature":"results-list","includeSections":"/mandarin/xinwenkuaixun","offset":0,"query":"display_date:[{date_range_item}]","size":20}}',
                'filter': '{content_elements{_id,credits{by{additional_properties{original{byline}},name,type,url}},description{basic},display_date,headlines{basic},label{basic{display,text,url}},owner{sponsored},promo_items{basic{_id,auth{1},type,url},lead_art{promo_items{basic{_id,auth{1},type,url}},type}},type,websites{rfa-mandarin{website_section{_id,name},website_url}}},count,next}',
                'd': '148',
                'mxId': '00000000',
                '_website': 'rfa-mandarin',
            }
            yield scrapy.Request(
                f'{url}?{parse.urlencode(params)}',
                callback=self.parse,
            )

    def parse_detail(self, response):
        d1 = response.xpath('//article[@class="b-article-body"]')
        clean_text = d1.xpath('.//p[@class="c-paragraph"]').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p:
                # print(_p)
                txt_list.append(_p)
        itm = response.meta['item']
        # print('\n'.join(txt_list))
        itm['content'] = '\n'.join(txt_list)
        if not itm['content']:
            itm['content'] = 'content'

        try:
            mod_time = re.search('"dateModified" ?: ?"(.*?)"', response.text).group(1)
            mod_time = self.to_utc_string(mod_time)
            if mod_time:
                itm['mod_time'] = mod_time
        except:
            pass

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

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
        try:
            for itm in response.json()['content_elements']:
                try:
                    url = itm['websites']['rfa-mandarin']['website_url']
                    if not url:
                        continue
                    if not url.startswith('http'):
                        url = parse.urljoin('https://www.rfa.org', url)
                    if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                        continue
                    title = itm['headlines']['basic']
                    if not title:
                        continue
                    pub_time = self.to_utc_string(itm['display_date'])
                    if not pub_time:
                        continue
                    # 检查过期资讯并过滤
                    if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                        self.logger.info(f'新闻过期：{pub_time}|{url}')
                        continue

                    mod_time = ''
                    desc = itm['description'].get('basic') or ''
                    lang = ''
                    content = ''
                    source = ''
                    keywords = ''
                    images = [{'url': ((itm.get('promo_items') or {}).get('basic') or {}).get('url') or '', 'caption': '', 'img_time': ''}]

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
                except Exception as e:
                    self.logger.error(f'解析itm失败：{url}，错误信息：{e}')
        except Exception as e:
            self.logger.error(f'解析失败：{response.request.url}，错误信息：{e}')
            return
                
