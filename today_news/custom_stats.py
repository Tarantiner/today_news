# custom_stats.py
from scrapy.statscollectors import StatsCollector
import datetime
import logging


class CustomStatsCollector(StatsCollector):

    def close_spider(self, spider, reason):
        """修改原始统计输出，添加spider名和本地时间"""

        # 1. 添加spider名称到统计信息
        if spider:
            self._stats['spider'] = spider.name

        # 2. 转换时间为本地时间
        if 'start_time' in self._stats:
            self._stats['start_time'] = self._convert_to_local_time(self._stats['start_time'])

        if 'finish_time' in self._stats:
            self._stats['finish_time'] = self._convert_to_local_time(self._stats['finish_time'])

        # 3. 调用父类方法输出修改后的统计信息
        super().close_spider(spider, reason)

    def _convert_to_local_time(self, time_val):
        """将时间转换为本地时间"""
        if isinstance(time_val, datetime.datetime):
            # UTC时间转本地时间
            return time_val.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
        elif isinstance(time_val, str):
            # 如果是字符串格式的时间，尝试转换
            try:
                # 处理带Z的UTC时间
                if time_val.endswith('Z'):
                    time_val = time_val[:-1] + '+00:00'
                dt = datetime.datetime.fromisoformat(time_val)
                return dt.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
            except:
                return time_val
        return time_val