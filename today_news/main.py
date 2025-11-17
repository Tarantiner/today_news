from scrapy import cmdline


if __name__ == '__main__':
    # 支持的城市列表在lib目录的en_city.json中
    # 新房(loupan): crawl new_house 旧房(xiaoqu): crawl old_house
    # 若直接cmd运行: scrapy crawl new_house -a province=湖北 -a city=武汉
    # cmdline.execute("scrapy crawl new_house -a province=湖北 -a city=武汉".split())
    # cmdline.execute("scrapy crawl new_house -a province=湖北 -a city=武汉 -o new_house.csv".split())
    # cmdline.execute("scrapy crawl old_house -a province=湖北 -a city=宜昌 -o old_house.csv".split())
    # cmdline.execute("scrapy crawl old_house -a province=湖北 -a city=宜昌".split())
    # cmdline.execute("scrapy crawl old_house -a province=北京 -a city=北京".split())

    # cmdline.execute("scrapy crawl apnews".split())
    # cmdline.execute("scrapy crawl chinatimes".split())
    # cmdline.execute("scrapy crawl worldjournal".split())
    cmdline.execute("scrapy crawl tvbs".split())

