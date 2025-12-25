# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from scrapy.pipelines.images import ImagesPipeline
from scrapy.exceptions import DropItem
from scrapy.utils.python import to_bytes
import hashlib
import traceback
import pymysql
import logging
import scrapy
import langid
import base64
import os


class DropPipeline:
    """数据验证管道"""

    def process_item(self, item, spider):
        if not item.get('title'):
            raise DropItem(f"缺少标题字段|{item.get('url')}")
        if not item.get('content'):
            raise DropItem(f"缺少内容字段|{item.get('url')}")
        if not item.get('pub_time'):
            raise DropItem(f"缺少发布时间字段|{item.get('url')}")
        return item


class DupePipeline:
    """去重管道"""

    def __init__(self):
        self.urls_seen = set()

    def process_item(self, item, spider):
        if item['url'] in self.urls_seen:
            raise DropItem(f"重复项目: {item['url']}")
        self.urls_seen.add(item['url'])
        return item


class CleanPipeline:
    """再次清洗管道，处理语言，统一时间等"""
    supported_langs = [
        'af', 'am', 'an', 'ar', 'as', 'az', 'be', 'bg', 'bn', 'br', 'bs',
        'ca', 'cs', 'cy', 'da', 'de', 'dz', 'el', 'en', 'eo', 'es', 'et',
        'eu', 'fa', 'fi', 'fo', 'fr', 'ga', 'gl', 'gu', 'he', 'hi', 'hr',
        'ht', 'hu', 'hy', 'id', 'is', 'it', 'ja', 'jv', 'ka', 'kk', 'km',
        'kn', 'ko', 'ku', 'ky', 'la', 'lb', 'lo', 'lt', 'lv', 'mg', 'mk',
        'ml', 'mn', 'mr', 'ms', 'mt', 'nb', 'ne', 'nl', 'nn', 'no', 'oc',
        'or', 'pa', 'pl', 'ps', 'pt', 'qu', 'ro', 'ru', 'rw', 'se', 'si',
        'sk', 'sl', 'sq', 'sr', 'sv', 'sw', 'ta', 'te', 'th', 'tl', 'tr',
        'ug', 'uk', 'ur', 'vi', 'vo', 'wa', 'xh', 'zh', 'zu'
    ]

    def process_item(self, item, spider):
        # 统一修改时间规范
        if not item['mod_time']:
            item['mod_time'] = '1970-01-01 00:00:00'

        # 统一语言规范
        lang = item['lang'].lower()
        if lang:
            if 'zh-' in lang or 'zh_' in lang:
                lang = 'zh'
            elif lang == 'eng' or 'en-' in lang or 'en_' in lang:
                lang = 'en'
            elif lang == 'spa':
                lang = 'es'
            elif lang not in self.supported_langs:
                try:
                    lang1 = langid.classify(item["title"]+item["desc"])[0]
                    print(f'处理了新语言{lang}-{lang1}', item['url'])
                    lang = lang1
                except:
                    lang = ""
        else:
            try:
                lang = langid.classify(item["title"] + item["desc"])[0]
                print(f'处理了没语言{lang}', item['url'])
            except:
                lang = ""
        item["lang"] = lang

        if 'is_origin' not in item:
            item['is_origin'] = True

        item['content'] = item['content'].replace('\xa0', ' ')
        item['desc'] = item['desc'].replace('\xa0', ' ')

        return item


class RobustImagesPipeline(ImagesPipeline):
    """下载新闻图片管道"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    # def file_path(self, request, response=None, info=None, *, item=None):
    #     """
    #     自定义图片保存路径和文件名
    #     这里我们强制使用 URL 的 MD5 作为文件名（带原始扩展名）
    #     """
    #     image_guid = hashlib.sha1(to_bytes(request.url)).hexdigest()  # noqa: S324
    #     return f"full/{image_guid}.jpg.temp"

    def get_media_requests(self, item, info):
        """为每个图片URL创建请求"""
        for image in item.get('images', []):
            if image.get('url') and image['url'].startswith('http'):
                yield scrapy.Request(
                    image['url'],
                )
                break

    def item_completed(self, results, item, info):
        """处理下载完成的图片"""
        image_info = {}

        for success, info in results:
            if success:
                # 下载成功
                lis = [i['caption'] for i in item['images'] if i['url']==info['url']]
                image_caption = lis[0] if len(lis)>=1 else ''
                image_info = {'checksum': info['checksum'], 'file_path': info['path'], 'caption': image_caption, 'url': info['url']}
                break
            else:
                self.logger.warning(f"图片下载失败")

        # 即使有图片下载失败，也返回item
        item['image_info'] = image_info
        return item

    def handle_download_error(self, failure, request, info):
        """处理下载错误 - 重写此方法以避免抛出异常"""
        self.logger.warning(f"图片下载错误: {request.url}, {failure.value}")
        # 不调用父类方法，避免抛出异常
        return None


class MysqlPipeline:
    def __init__(self, mysql_conf):
        self.mysql_conf = mysql_conf
        self.conn = None
        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            mysql_conf=crawler.settings.get("MYSQL_CONFIG"),
        )

    def get_connection(self):
        """每次获取连接时都检查状态，确保连接有效"""
        try:
            # 如果连接存在且开启，ping一下检查状态
            if self.conn and self.conn.open:
                self.conn.ping(reconnect=True)  # 关键：自动重连
                return self.conn
        except Exception as e:
            # 连接异常，重置为None
            self.logger.error(f'mysql连接异常|{type(e)}')
            self.conn = None

        # 创建新连接
        self.conn = pymysql.connect(**self.mysql_conf)
        self.logger.info(f'已开启mysql连接')
        return self.conn

    def open_spider(self, spider):
        return

    def close_spider(self, spider):
        if self.conn:
            try:
                self.conn.close()
                self.logger.info(f'已关闭mysql连接')
            except:
                pass

    def process_item(self, item, spider):
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                # 插入封面
                image_info = item.get('image_info') or {}
                cover_id = image_info.get('checksum') or ''
                image_path = image_info.get('file_path') or ''
                # if image_path:
                #     try:
                #         url_sha1_name = image_path.split('/')[1].split('.')[0]
                #         md5_path = image_path.replace(url_sha1_name, cover_id).rstrip('.temp')
                #         old_path = os.path.join(spider.settings.get('IMAGES_STORE'), image_path)
                #         new_path = old_path.replace(url_sha1_name, cover_id).rstrip('.temp')
                #         os.rename(old_path, new_path)
                #         image_path = md5_path
                #     except:
                #         image_path = ''
                caption = image_info.get('caption') or ''

                if cover_id and image_path:
                    cover_sql_str = 'INSERT IGNORE INTO cover (checksum, filepath, caption) VALUES (%s, %s, %s)'
                    cursor.execute(cover_sql_str, (cover_id, image_path, caption))

                # 插入新闻
                article_sql_str = '''
                INSERT IGNORE INTO news 
                (url, source, title, `desc`, keywords, content, lang, pub_time, mod_time, name, cover_id) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                '''
                cursor.execute(article_sql_str, (
                    item['url'].strip(),
                    item['source'].strip(),
                    item['title'].strip(),
                    item['desc'].strip(),
                    item['keywords'].strip(),
                    item['content'].strip(),
                    item['lang'].strip(),
                    item['pub_time'].strip(),
                    item['mod_time'].strip(),
                    item['name'].strip(),
                    image_info.get('checksum') or ''
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f'数据入库失败|{type(e)}')

        if item.get('content') == 'content':
            raise DropItem(f"没有内容: {item['url']}")
        return item


class ImageProcessPipeline:
    """图片处理成base64注入到数据里"""

    def process_item(self, item, spider):
        image_info = item.get('image_info') or {}
        image_path = image_info.get('file_path') or ''
        if image_path:
            file_path = os.path.join(spider.settings.get('IMAGES_STORE'), image_path)
            if not os.path.exists(file_path):
                item['image_info'] = {}
            else:
                try:
                    with open(file_path, 'rb')as f:
                        b = base64.b64encode(f.read()).decode()
                    image_info.pop('file_path', None)
                    image_info['data'] = b
                except:
                    print(f'处理图片异常|{traceback.format_exc()}')
                    item['image_info'] = {}
        else:
            item['image_info'] = {}

        return item
