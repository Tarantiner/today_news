from datetime import datetime, timedelta


class SpiderTxtParser:
    def clean_phrase(self, txt):
        return txt.strip(' \r\n\t\xa0👉&nbsp\u200b')


class SpiderUtils:
    def match_invalid_url(self, url):
        return False

    def check_expire_news(self, utc_time_str):
        # 解析UTC时间
        utc_time = datetime.strptime(utc_time_str, '%Y-%m-%d %H:%M:%S')

        # 转换为北京时间（UTC+8）
        beijing_time = utc_time + timedelta(hours=8)

        # 获取当前时间（假设系统时间是北京时间）
        current_time = datetime.now()

        # 计算一天前的时间边界（00:00:00）
        one_day_ago = current_time.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=1)

        # print(f"UTC时间: {utc_time}")
        # print(f"北京时间: {beijing_time}")
        # print(f"当前时间: {current_time}")
        # print(f"一天前边界: {one_day_ago}")
        # print(f"是否在一天前: {beijing_time < one_day_ago}")

        return beijing_time < one_day_ago
