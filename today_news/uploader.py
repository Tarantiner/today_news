import os
import time
import signal
import platform
import threading
import traceback
import logging
from threading import Thread
import requests


# 存放json文件的路径
data_json_path = r'F:\news_exports\exports'
# 存放资源文件的路径
data_media_path = r'F:\news_cover\full'
# json文件上传url
file_upload_uri = '/file/uploadFile'
# 资源文件上传url
media_upload_uri = '/file/uploadMedia'
# 服务接口
host_server = 'http://172.16.201.131:9005'


def request_post_file(url, file_path):
    """
    requests POST 上报文件
    :param url:
    :param files:
    :param callback: 上传进度 : def callback(percentage, msg)
    :return: True or False
    """
    r = None
    status = False
    msg = ''
    try:
        # 打开文件，并获取文件大小
        file_size = os.path.getsize(file_path)
        with open(file_path, 'rb') as file:
            file_name = os.path.basename(file_path)
            r = requests.post(url, files={'file': (file_name, file)},
                                     headers={'Content-Length': str(file_size)}, timeout=30)
            if r.status_code in [200, 201] and r.json()['status'] is True:
                status = True
            elif r.status_code == 404:
                msg = f"找不到文件上传url:{url}"
            else:
                msg = r.text
    except requests.HTTPError as e:
        msg = str(e)
    except requests.ConnectionError as e:
        msg = str(e)
    except requests.Timeout as e:
        msg = str(e)
    finally:
        if r:
            r.close()
    return status, msg


class ContinuePostDataFileThread(threading.Thread):
    def __init__(self, log_control, stop_event):
        super().__init__()
        self.log = log_control
        self.stop_event = stop_event

    def upload_data(self, uri, filepath, _type=''):
        # self.log.info(f'文件续传|正在上传{_type}文件|{filepath}')
        url = "{}{}".format(host_server, uri)
        try:
            status, err = request_post_file(url, filepath)
        except Exception as e:
            self.log.error(f'文件续传|上传{_type}文件失败1|{filepath}|{traceback.format_exc()}')
            return False
        if not status:
            self.log.error(f'文件续传|上传{_type}文件失败2|{filepath}|{err}')
            return False
        else:
            self.log.info(f'文件续传|上传{_type}文件成功|{filepath}')
            os.remove(filepath)
            return True

    def process_json(self):
        while not self.stop_event.is_set():
            file_list = []
            for file_name in os.listdir(data_json_path):
                # file_info = os.stat(os.path.join(data_json_path, file_name))
                # if file_info.st_size == 0:
                #     continue
                # if int(time.time() - file_info.st_ctime) < 60:
                #     continue
                if file_name.endswith('.jsonl'):
                    file_list.append(file_name)

            if not file_list:
                self.log.info(f'暂无可处理json')
            else:
                self.log.info(f'{len(file_list)}个json文件待上传')
                for file in file_list:
                    if self.stop_event.is_set():
                        break
                    filepath = os.path.join(data_json_path, file)
                    if not os.path.exists(filepath):
                        self.log.warning(f'文件续传|json上传目录文件已不存在|{filepath}')
                        continue
                    self.upload_data(file_upload_uri, filepath, _type='数据')
            time.sleep(10)
        else:
            self.log.info(f'文件续传|处理json文件续传已收到结束信号')

    def process_media(self):
        while not self.stop_event.is_set():
            file_list = []
            for file_name in os.listdir(data_media_path):
                file_info = os.stat(os.path.join(data_media_path, file_name))
                if file_info.st_size == 0:
                    continue
                if int(time.time() - file_info.st_ctime) < 60:
                    continue
                file_list.append(file_name)

            if not file_list:
                self.log.info(f'暂无可处理media')
            else:
                self.log.info(f'{len(file_list)}个media文件待上传')
                for file in file_list:
                    if self.stop_event.is_set():
                        break
                    filepath = os.path.join(data_media_path, file)
                    if not os.path.exists(filepath):
                        self.log.warning(f'文件续传|media上传目录文件已不存在|{filepath}')
                        continue
                    self.upload_data(media_upload_uri, filepath, _type='媒体')
            time.sleep(10)
        else:
            self.log.info(f'文件续传|处理media文件续传已收到结束信号')

    def run(self):
        # Thread(target=self.process_media).start()
        self.process_json()


def on_exit(signalnum, frame, stop_event):
    print('收到结束信号. signalnum({}), frame({})'.format(signalnum, frame))
    stop_event.set()


if __name__ == '__main__':
    stop_event = threading.Event()
    sig_list = []
    sig_list.append(signal.SIGINT)
    if platform.system() == 'Linux':
        sig_list.append(signal.SIGTERM)
    for sig in sig_list:
        signal.signal(sig, lambda sig, frame: on_exit(sig, frame, stop_event))
    logging.basicConfig(level=logging.INFO, format='%(asctime)s * %(thread)d] [%(levelname)s] %(message)s')
    logger = logging.getLogger('uploader.log')
    ContinuePostDataFileThread(logger, stop_event).start()

