import re
import os
import scrapy
import datetime
import traceback
from urllib import parse
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered


# {'时政', '视频', '文化', '经济', '社会', '环保', '科技', '国际', ' 播客', '体育', '旅游', ' 图片'}
class VietnamplusSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "越南通讯社"
    allowed_domains = ["vietnamplus.vn"]

    async def start(self):
        base_url = 'https://zh-api.vietnamplus.vn/api/morenews-topic-107-{}.html?phrase=&page_size=20&sz=107&st=topic'
        page = 1

        # 先请求第一页，用于判断是否继续
        first_url = base_url.format(page)
        yield scrapy.Request(
            first_url,
            callback=self.parse_with_continuation,
            headers={
                'referer': 'https://zh.vietnamplus.vn/topic/tp-107.vnp',
            },
            meta={
                'base_url': base_url,
                'current_page': page,
                'is_first': True
            }
        )

    def match_invalid_url(self, cate):
        # {'时政', '视频', '文化', '经济', '社会', '环保', '科技', '国际', ' 播客', '体育', '旅游', ' 图片'}
        if cate in ('时政', '经济', '社会', '国际'):
            return False
        return True

    def parse_detail(self, response):
        d1 = response.xpath('//div[@itemprop="articleBody"]')
        clean_text = d1.xpath('./p').xpath('string(.)')
        txt_list = []
        for p in clean_text.extract():
            _p = self.clean_phrase(p)
            if _p:
                for __p in _p.split('。  '):
                    __p = self.clean_phrase(__p)
                    if __p:
                        # print([__p])
                        txt_list.append(__p)
        itm = response.meta['item']
        # print('\n'.join(txt_list))
        itm['content'] = '\n'.join(txt_list)
        if not itm['content']:
            itm['content'] = 'content'

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

    def parse_with_continuation(self, response):
        base_url = response.meta['base_url']
        current_page = response.meta['current_page']
        is_first = response.meta.get('is_first', False)
        should_continue = True

        try:
            for itm in response.json()['data']['contents']:
                url = itm.get('url') or ''
                if not url:
                    continue
                cate = (itm.get('zone') or {}).get('name') or ''
                if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(cate):
                    continue
                title = self.clean_phrase(itm.get('title') or '')
                if not title:
                    continue
                pub_time = self.to_utc_string(itm.get('date'))
                # 检查过期资讯并过滤
                if self.settings.get('ENABLE_NEWS_TIME_FILTER') and self.check_expire_news(pub_time, self.settings.get(
                        'NEWS_EXPIRE_DAYS')):
                    self.logger.info(f'新闻过期：{pub_time}|{url}')
                    if should_continue:
                        should_continue = False
                    continue

                mod_time = self.to_utc_string(itm.get('update_time'))
                desc = remove_tags(itm.get('description') or '')
                lang = ''
                content = ''
                source = itm.get('source') or ''
                keywords = ''

                img_list = [itm.get('avatar_url') or ''] if itm.get('avatar_url') else []
                if img_list:
                    img_url = img_list[0]
                    img_caption = itm.get('avatar_description') or ''
                    img_time = ''
                    images = [
                        {'url': img_url, 'caption': img_caption, 'img_time': img_time}
                    ]
                    images = images
                else:
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
                                     headers={
                                         'referer': 'https://zh.vietnamplus.vn/topic/tp-107.vnp',
                                     },
                                     callback=self.parse_detail, errback=self.parse_detail_failed)
        except Exception as e:
            self.logger.error(f'解析内容异常|{traceback.format_exc()}')
            return

        if not response.json()['data'].get('load_more'):
            print('没有更多新闻了')
            return

        if should_continue:
            next_page = current_page + 1
            next_url = base_url.format(next_page)
            print('继续访问', next_url)

            yield scrapy.Request(
                next_url,
                callback=self.parse_with_continuation,
                headers={
                    'referer': 'https://zh.vietnamplus.vn/topic/tp-107.vnp',
                },
                meta={
                    'base_url': base_url,
                    'current_page': next_page,
                    'is_first': False
                }
            )
        else:
            print('应当停止', response.url)

    # def parse(self, response):
    #     if response.request.url == self.start_urls[0]:
    #         response.selector.remove_namespaces()
    #         lis = []
    #         for link in response.xpath('//loc/text()').extract():
    #             if link and 'sitemap' in link:
    #                 try:
    #                     x = re.search('newsdig.tbs.co.jp/common/files/sitemap-(\d+?)-(\d+?).xml', link)
    #                     lis.append((link, int(x.groups()[0] + x.groups()[1])))
    #                 except:
    #                     continue
    #         for url_itm in sorted(lis, key=lambda x: x[1], reverse=True)[:2]:
    #             return scrapy.Request(url_itm[0], callback=self.parse_target_site)
