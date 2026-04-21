import scrapy
from w3lib.html import remove_tags_with_content, remove_comments, remove_tags
from today_news.spiders.spider_helper import SpiderTxtParser, SpiderUtils
from today_news.items import TodayNewsItem
from today_news.middlewares import DupeFiltered

class InquirerFxSpider(scrapy.Spider, SpiderTxtParser, SpiderUtils):
    name = "每日询问报"
    allowed_domains = ["inquirer.net"]
    start_urls = ["https://globalnation.inquirer.net/category/latest-stories/page/1"]
    custom_settings = {
        'CONCURRENT_REQUESTS': 16,
        'DOWNLOAD_DELAY': 2,
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36 Edg/142.0.0.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Priority': 'u=0, i',
            'Sec-Ch-Device-Memory': '8',
            'Sec-Ch-Ua': '"Chromium";v="142", "Microsoft Edge";v="142", "Not_A Brand";v="99"',
            'Sec-Ch-Ua-Mobile': '?1',
            'Sec-Ch-Ua-Model': '"Nexus 5"',
            'Sec-Ch-Ua-Platform': '"Android"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        }
    }

    def parse_detail(self, response):
        itm = response.meta['item']

        clean_text = response.xpath('//div[@id="FOR_target_content"]/p/text()')
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

        desc = response.xpath('//meta[@name="description"]/@content').extract_first('')
        if desc:
            itm['desc'] = desc

        source = response.xpath('//meta[@name="author"]/@content').extract_first('')
        if source:
            itm['source'] = source

        if not itm.get('images'):
            img_list = response.xpath('//meta[@property="og:image"]')
            if img_list:
                img_url = response.urljoin(img_list[0].xpath('./@content').extract_first(''))
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
        response.selector.remove_namespaces()
        has_expired_news = False
        news_count = 0
        
        for itm in response.xpath('//div[@id="inq-channel-left"]/div[@id="ch-ls-box"]'):
            url = response.urljoin(itm.xpath('./div[@id="ch-ls-head"]/h2/a/@href').extract_first(''))
            if not url:
                continue
            if self.settings.get('ENABLE_NEWS_URL_FILTER') and self.match_invalid_url(url):
                continue
            title = itm.xpath('./div[@id="ch-ls-head"]/h2/a/text()').extract_first('')
            time_class = itm.xpath('./div[@id="ch-ls-head"]/div[@id="ch-postdate"]/span/text()').extract_first('')
            print("time_class:", time_class)
            time_str = time_class.replace('January', '01').replace('February', '02').replace('March', '03').replace('April', '04').replace('May', '05').replace('June', '06').replace('July', '07').replace('August', '08').replace('September', '09').replace('October', '10').replace('November', '11').replace('December', '12')
            pub_time_str = time_str.split(',')[1].strip() + '-' + time_str.split(',')[0].replace(' ', '-').strip() + ' 00:00:00'
            pub_time = self.to_utc_string(self.name,pub_time_str)
            if not pub_time:
                continue
            news_count += 1
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
            yield scrapy.Request(url, meta={'snapshot': True, 'item': itm, 'detail': True},
                                 callback=self.parse_detail, errback=self.parse_detail_failed)
        
        if news_count == 0:
            self.logger.info(f'页面无新闻条目，停止翻页: {response.url}')
            return
        
        if not has_expired_news:
            current_page = 1
            if '/page/' in response.url:
                current_page = int(response.url.split('/page/')[-1].split('/')[0])
            next_page = current_page + 1
            next_url = f"https://globalnation.inquirer.net/category/latest-stories/page/{next_page}"
            yield scrapy.Request(next_url, callback=self.parse)
