# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from scrapy.pipelines.images import ImagesPipeline
from scrapy.exceptions import DropItem
import pymysql
import logging
import scrapy


class DropPipeline:
    """数据验证管道"""

    def process_item(self, item, spider):
        if not item.get('title'):
            raise DropItem("缺少标题字段")
        if not item.get('content'):
            raise DropItem("缺少内容字段")
        if not item.get('pub_time'):
            raise DropItem("缺少发布时间字段")
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


class RobustImagesPipeline(ImagesPipeline):
    """下载新闻图片管道"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(__name__)

    def get_media_requests(self, item, info):
        """为每个图片URL创建请求"""
        for image in item.get('images', []):
            if image.get('url'):
                yield scrapy.Request(
                    image['url'],
                    meta={'image_info': image, 'item': item}
                )

    def item_completed(self, results, item, info):
        """处理下载完成的图片"""
        image_paths = []

        for result in results:
            print('图片结果', result)
            success, image_info = result
            original_image = image_info.get('meta', {}).get('image_info', {})

            if success:
                # 下载成功
                original_image['downloaded'] = True
                original_image['local_path'] = image_info['path']
                image_paths.append(image_info['path'])
            else:
                # 下载失败，记录错误但不中断
                original_image['downloaded'] = False
                original_image['error'] = 'Download failed'  # {'url': xx, 'caption': xx, 'img_time': xx, 'download': False, 'error': 'Download failed'}
                self.logger.warning(f"图片下载失败: {original_image.get('url')}")

        # 即使有图片下载失败，也返回item
        item['image_paths'] = image_paths
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
                sql_str = '''
                INSERT IGNORE INTO news 
                (url, source, title, `desc`, content, lang, pub_time, mod_time) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                '''
                cursor.execute(sql_str, (
                    item['url'].strip(),
                    item['source'].strip(),
                    item['title'].strip(),
                    item['desc'].strip(),
                    item['content'].strip(),
                    item['lang'].strip(),
                    item['pub_time'].strip(),
                    item['mod_time'].strip(),
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f'数据入库失败|{type(e)}')

        return item

