import re
from datetime import datetime, timezone, timedelta
from dateutil import parser


class SpiderTxtParser:
    def clean_phrase(self, txt):
        return txt.strip(' \r\n\t\xa0👉&nbsp\u200b')


class SpiderUtils:
    # 常见时间格式的正则表达式
    patterns = {
        'iso_8601': r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?',
        'simple_iso': r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
        'timestamp': r'^\d{10,13}$',  # 10位秒级或13位毫秒级时间戳
    }

    def parse_time(self, time_str):
        """
        通用时间解析方法
        """
        if not time_str:
            return None

        time_str = str(time_str).strip('\n ')

        # 1. 先尝试使用dateutil.parser（最通用）
        try:
            dt = parser.parse(time_str)
            return self._to_utc_datetime(dt)
        except:
            pass

        # 2. 尝试解析时间戳
        if re.match(self.patterns['timestamp'], time_str):
            return self._parse_timestamp(time_str)

        # 3. 尝试修复常见格式问题
        fixed_str = self._fix_common_format_issues(time_str)
        if fixed_str != time_str:
            try:
                dt = parser.parse(fixed_str)
                return self._to_utc_datetime(dt)
            except:
                pass

        # 4. 尝试自定义解析
        return self._custom_parse(time_str)

    def _parse_timestamp(self, timestamp_str):
        """解析时间戳"""
        try:
            ts = float(timestamp_str)

            # 判断是秒级还是毫秒级时间戳
            if ts > 1e12:  # 大于1970年的秒数？可能是毫秒
                ts = ts / 1000.0

            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return dt
        except:
            return None

    def _fix_common_format_issues(self, time_str):
        """修复常见的时间格式问题"""
        # 修复类似 "2025-12-16T19:01:44.58:3Z" 的格式
        if re.search(r'\.\d{1,2}:\d{1,2}[Z+-]', time_str):
            # 将 "58:3Z" 转换为 "58.3Z"
            time_str = re.sub(r'\.(\d{1,2}):(\d{1,2})([Z+-])', r'.\1.\2\3', time_str)

        # 修复时区格式问题
        time_str = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', time_str)

        # 修复缺少秒数的情况
        if re.match(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}[Z+-]', time_str):
            time_str = re.sub(r'(\d{2}:\d{2})([Z+-])', r'\1:00\2', time_str)

        return time_str

    def _custom_parse(self, time_str):
        """自定义解析逻辑"""
        formats_to_try = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%d %H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S.%f%z',
            '%Y-%m-%d %H:%M:%S.%f%z',
        ]

        for fmt in formats_to_try:
            try:
                dt = datetime.strptime(time_str, fmt)
                return self._to_utc_datetime(dt)
            except:
                continue

        # 尝试解析带有时区偏移的格式
        tz_patterns = [
            (r'(.*)([+-]\d{2}):(\d{2})$', '%Y-%m-%d %H:%M:%S%z'),
            (r'(.*T.*)([+-]\d{2})(\d{2})$', '%Y-%m-%dT%H:%M:%S%z'),
        ]

        for pattern, fmt in tz_patterns:
            match = re.match(pattern, time_str)
            if match:
                try:
                    # 重建标准时区格式
                    base = match.group(1)
                    tz_hour = match.group(2)
                    tz_min = match.group(3)
                    fixed_str = f"{base}{tz_hour}:{tz_min}"
                    dt = datetime.strptime(fixed_str, fmt)
                    return self._to_utc_datetime(dt)
                except:
                    continue

        return None

    def _to_utc_datetime(self, dt):
        """将datetime对象转换为UTC时区"""
        if dt.tzinfo is None:
            # 如果没有时区信息，假设为本地时间
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            # 转换为UTC
            dt = dt.astimezone(timezone.utc)
        return dt

    def to_utc_string(self, time_str):
        """转换为UTC时间字符串"""
        dt = self.parse_time(time_str)
        if dt:
            utc_time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            # print(f'{time_str:45} -> {utc_time_str}')
            return utc_time_str
        print(f'提取时间失败：【{time_str}】')
        return ''

    def match_invalid_url(self, url):
        if '/video/' in url:
            return True
        return False

    def check_expire_news(self, utc_time_str, expire_days):
        # 解析UTC时间
        utc_time = datetime.strptime(utc_time_str, '%Y-%m-%d %H:%M:%S')

        # 转换为北京时间（UTC+8）
        beijing_time = utc_time + timedelta(hours=8)

        # 获取当前时间（假设系统时间是北京时间）
        current_time = datetime.now()

        # 计算时间边界（00:00:00）
        days_ago = current_time.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=expire_days)

        # print(f"UTC时间: {utc_time}")
        # print(f"北京时间: {beijing_time}")
        # print(f"当前时间: {current_time}")
        # print(f"一天前边界: {one_day_ago}")
        # print(f"是否在一天前: {beijing_time < one_day_ago}")

        return beijing_time < days_ago

if __name__ == '__main__':
    # 使用示例
    ps = SpiderUtils()

    test_cases = [
        "2025-11-09 16:46:27-05:00",
        "2025-12-16T19:01:44.58:3Z",  # 有问题的格式
        "2025-12-16T19:01:44.583Z",
        "2025-12-17T02:30:00Z",
        "2025-12-17T02:26:02.365000+00:00",
        "1765916909",  # 时间戳
        "1765916909123",  # 毫秒时间戳
        "2025-12-16 19:01:44",
        "2025/12/16 19:01:44",
    ]

    for test in test_cases:
        result = ps.to_utc_string(test)
