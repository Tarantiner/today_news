# storage/completed_file_storage.py
import os
from pathlib import Path
from scrapy.extensions.feedexport import FileFeedStorage


class CompletedFileFeedStorage(FileFeedStorage):
    """
    自定义 FileFeedStorage：
    - 写入时使用临时文件（原路径 + .part）
    - 完成后重命名为 原路径 + .completed
    """
    TEMP_SUFFIX = ".part"  # 写入过程中的临时后缀

    def __init__(self, uri, *, feed_options=None):
        super().__init__(uri)
        # 临时写入路径（.part）
        self.temp_path = self.path + self.TEMP_SUFFIX

    def open(self, spider):
        dirname = Path(self.path).parent
        if dirname and not dirname.exists():
            dirname.mkdir(parents=True)
        return Path(self.temp_path).open(self.write_mode)

    def store(self, file):
        # 先关闭文件（如果还没关闭）
        file.close()
        # 重命名为最终的 .completed 文件
        if os.path.exists(self.temp_path):
            os.rename(self.temp_path, self.path)
