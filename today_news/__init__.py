import json
import requests


# 节点id
node_id = 'node_001'
# 服务接口
host_server = 'http://172.16.201.131:9005'
# 获取任务
task_uri = '/task/getTask'

test_mode = True

if test_mode:
    try:
        SPIDER_SETTINGS = json.load(open('./spider_settings.json', 'r', encoding='utf-8'))
        print(SPIDER_SETTINGS)
    except:
        import traceback
        print(traceback.format_exc())
        SPIDER_SETTINGS = {}
else:
    for _ in range(5):
        try:
            res = requests.get(f'{host_server}{task_uri}?node_id={node_id}')
            SPIDER_SETTINGS = res.json()['data'][0]
            print(SPIDER_SETTINGS)
            break
        except:
            pass
    else:
        SPIDER_SETTINGS = {}
