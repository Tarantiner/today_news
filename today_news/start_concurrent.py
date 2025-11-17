import multiprocessing as mp
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings


def run_spiders_chunk(spider_chunk, settings):
    """运行一批spider"""
    process = CrawlerProcess(settings)

    for spider_name in spider_chunk:
        print(f"启动: {spider_name}")
        process.crawl(spider_name)

    process.start()


if __name__ == "__main__":
    # 获取所有spider
    settings = get_project_settings()
    master_process = CrawlerProcess(settings)
    all_spiders = list(master_process.spider_loader.list())

    # 分成10组
    num_chunks = 10
    chunk_size = len(all_spiders) // num_chunks + 1
    chunks = [all_spiders[i:i + chunk_size] for i in range(0, len(all_spiders), chunk_size)]

    # 多进程执行
    processes = []
    for i, chunk in enumerate(chunks):
        p = mp.Process(target=run_spiders_chunk, args=(chunk, settings))
        p.start()
        processes.append(p)
        print(f"启动进程 {i + 1}, 处理 {len(chunk)} 个spider")

    for p in processes:
        p.join()

    print("🎉 所有爬虫执行完成！")