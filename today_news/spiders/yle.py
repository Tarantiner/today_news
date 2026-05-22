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


class YleSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "芬兰广播公司"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.should_stop = False
        self.twenty_four_hours_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)

    def get_utc3_time_str(self):
        """生成东三区(UTC+3)的时间字符串，格式为 '%Y-%m-%dT%H:%M:%S'"""
        dt = datetime.datetime.now(datetime.timezone.utc)
        utc3_time = dt + datetime.timedelta(hours=3)
        return utc3_time.strftime('%Y-%m-%dT%H:%M:%S')

    def start_requests(self):
        """开始请求，生成第一个API请求"""
        headers = {
            'accept': 'application/json, text/plain, */*',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
        }
        before_time = self.get_utc3_time_str()
        url = self._build_api_url(before_time)
        yield scrapy.Request(
            url,
            callback=self.parse_api_response,
            meta={
                'before_time': before_time,
                'headers': headers
            },
            headers=headers
        )

    def _build_api_url(self, before_time):
        """构建API请求URL"""
        return f'https://ca.api.yle.fi/v1/graphql?app_id=ukko_prod&app_key=12150df3a0c8844d37c520235bf7c5d4&query=query+tuoreimmatArticleListQuery+($limit:Int!$exclude:Exclude!$publishers:%5BYlePublisher%5D%3D+%5B%5D$editorialSections:%5BString%5D$publishedBefore:String+$publishedAfter:String+$fields:ArticleFields+%3DHEADLINE$language:String+)%7Btuoreimmat:+articleList+(+limit:$limit+exclude:$exclude+publishers:$publishers+editorialSections:$editorialSections+publishedBefore:$publishedBefore+publishedAfter:$publishedAfter+fields:$fields+language:$language+)%7Bitems%7Bid+title+fullUrl+lead+journalisticStyle+publisher%7Bname%7Dsubjects%7B...conceptFields%7DdatePublished+format+headline%7Bfull+short+image%7B...on+ImageBlock%7B...listItemImageBlockFields%7D%7Dvideo%7B...on+VideoBlock%7Bid+image%7B...listItemImageBlockFields%7D%7D%7Daudio%7B...on+AudioBlock%7Bid+image%7B...listItemImageBlockFields%7D%7D%7D%7DmainMedia%7Btype:__typename...on+ImageBlock%7B...listItemImageBlockFields%7D...on+AudioBlock%7Bid+image%7B...listItemImageBlockFields%7D%7D...on+VideoBlock%7Bid+offsetSeconds+image%7B...listItemImageBlockFields%7D%7D%7Dtopic%7Bid+isHidden+isLocked+acceptedCommentsCount%7D%7D%7D%7Dfragment+conceptFields+on+Concept%7Bid+alternativeIds+title%7Bfi+sv+se+en+uk+ru%7DshortTitle%7Bfi+sv+se+en+uk+ru%7D%7Dfragment+listItemImageBlockFields+on+ImageBlock%7Bid+alt+alts%7Blanguage+value%7Dcopyright%7Blanguage+value%7Dversion+blurhash+crops%7Baspect+coordinates%7Bheight+width+x+y%7D%7D%7D&variables=%7B%22limit%22:21,%22exclude%22:%7B%22properties%22:%5B%22importance:low%22,%22automaticListHint:never%22,%22automaticListHint:no-recently%22%5D,%22journalisticStyle%22:%5B%22non_journalistic_content%22%5D,%22coverage%22:%22LOCAL%22%7D,%22publishedBefore%22:%22{before_time}%2B0300%22,%22publishers%22:%5B%22YLE%22,%22YLE_UUTISET%22,%22YLE_URHEILU%22,%22YLE_ASIA%22,%22YLE_AIHE%22,%22YLE_LUME%22,%22YLE_KULTTUURI_JA_VIIHDE%22,%22YLEX%22,%22YLE_ELAVA_ARKISTO%22,%22YLE_UUTISLUOKKA%22%5D,%22language%22:%22fi%22%7D'

    def parse_api_response(self, response):
        """解析API响应，提取items并判断是否继续循环"""
        if self.should_stop:
            return

        try:
            data = json.loads(response.text)
            
            # 提取items
            items = data.get('data', {}).get('tuoreimmat', {}).get('items', [])
            
            if not items:
                self.logger.info('API返回空数据，停止循环')
                return

            # 记录最小时间
            min_pub_time = None
            
            for item in items:
                # 提取基本信息
                url = item.get('fullUrl', '')
                title = item.get('title', '')
                date_published = item.get('datePublished', '')
                
                # 解析发布时间
                pub_time = self.to_utc_string(self.name, date_published)
                
                # 更新最小时间
                if pub_time:
                    pub_dt = datetime.datetime.strptime(pub_time, '%Y-%m-%d %H:%M:%S')
                    pub_dt = pub_dt.replace(tzinfo=datetime.timezone.utc)
                    if min_pub_time is None or pub_dt < min_pub_time:
                        min_pub_time = pub_dt
                
                # 检查是否过期
                if pub_time and self.settings.get('ENABLE_NEWS_TIME_FILTER'):
                    if self.check_expire_news(pub_time, self.settings.get('NEWS_EXPIRE_DAYS')):
                        self.logger.info(f'新闻过期：{pub_time}|{url}')
                        if not self.should_stop:
                            self.should_stop = True
                        continue
                
                # 创建item并请求详情页
                itm = TodayNewsItem(
                    url=url,
                    pub_time=pub_time,
                    mod_time='',
                    title=title,
                    desc='',
                    lang='',
                    content='',
                    source='',
                    keywords='',
                    name=self.name,
                    images=[],
                )

                yield scrapy.Request(
                    url,
                    callback=self.parse_detail,
                    errback=self.parse_detail_failed,
                    meta={'snapshot': True, 'item': itm, 'detail': True}
                )
            
            # 继续下一页，使用最小时间作为下一次的before_time
            if min_pub_time is not None and not self.should_stop:
                # 转换为东三区时间格式
                utc3_time = min_pub_time + datetime.timedelta(hours=3)
                next_before_time = utc3_time.strftime('%Y-%m-%dT%H:%M:%S')
                
                headers = response.meta.get('headers', {})
                next_url = self._build_api_url(next_before_time)
                
                self.logger.info(f'继续请求下一页，before_time: {next_before_time}')
                
                yield scrapy.Request(
                    next_url,
                    callback=self.parse_api_response,
                    meta={
                        'before_time': next_before_time,
                        'headers': headers
                    },
                    headers=headers
                )

        except Exception as e:
            self.logger.error(f'解析API响应失败: {e}')
            traceback.print_exc()

    def parse_detail(self, response):
        """解析详情页"""
        itm = response.meta['item']
        
        # 提取正文内容
        d1 = response.xpath('//section[@class="yle__article__content"]')
        txt_list = []
        for p in d1.xpath('.//h2/text() | .//p//text()').extract():
            _p = self.clean_phrase(p)
            if _p:
                print([_p])
                txt_list.append(_p)
        itm['content'] = '\n'.join(txt_list)
        if not itm['content']:
            itm['content'] = 'content'

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        try:
            mod_time = re.search('"dateModified" ?: ?"(.*?)"', response.text).group(1)
            mod_time = self.to_utc_string(self.name, mod_time)
            if mod_time:
                itm['mod_time'] = mod_time
        except:
            pass

        # 提取图片
        if not itm.get('images'):
            img_list = response.xpath('//meta[@property="og:image"]')
            if img_list:
                img_url = img_list[0].xpath('./@content').extract_first('')
                img_caption = img_list[0].xpath('./@alt').extract_first('')
                images = [{
                    'url': img_url,
                    'caption': img_caption,
                    'img_time': ''
                }]
                itm['images'] = images

        if not itm.get('keywords'):
            itm['keywords'] = response.xpath('//meta[@name="keywords"]/@content').extract_first('')

        yield itm

    def parse_detail_failed(self, failure):
        """详情页请求失败处理"""
        return
