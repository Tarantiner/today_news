# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class TodayNewsItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    url = scrapy.Field()  # 链接
    pub_time = scrapy.Field()  # 发布时间
    mod_time = scrapy.Field()  # 更新（修改）时间
    title = scrapy.Field()  # 标题
    desc = scrapy.Field()  # 描述（摘要）
    lang = scrapy.Field()  # 语言
    content = scrapy.Field()  # 内容
    source = scrapy.Field()  # 来源
    keywords = scrapy.Field()  # 关键词
    name = scrapy.Field()  # 网站名（可以和来源不一致）
    images = scrapy.Field()  # 下载前图片信息
    image_info = scrapy.Field()  # 下载后图片信息

