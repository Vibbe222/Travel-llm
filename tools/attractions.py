import time
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup
from dotenv import find_dotenv, load_dotenv
from langchain_core.tools import tool
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.remote_connection import LOGGER
import logging
from typing import Annotated

MAX_SCENIC_SPOTS = 7


def InitWebDriver():
    LOGGER.setLevel(logging.WARNING)
    options = webdriver.ChromeOptions()
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                  get: () => undefined
                })
            """
        },
    )
    return driver
# 1.创建 Chrome 的启动配置
# 2.减少多余的不重要日志输出
# 3.加入一些“反自动化识别”设置
# 4.启动并返回一个可操作的浏览器对象


def fetch_page_with_selenium(driver, url):
    driver.get(url)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(1)
    return driver.page_source
# 用 Selenium 打开一个网页，等页面基本加载完成后，把当前网页的 HTML 源码返回出来。


def get_destination_overview(soup):
    overview_element = soup.find('span', {'id': 'mdd_poi_desc'})
    if overview_element:
        return overview_element.text.strip()
    return "Overview not found."
# 从已经解析好的网页 HTML 里，找到“目的地简介”那一块文字并返回；如果没找到，就返回一个默认提示。


def get_scenic_spot_details(driver, url, spot_name):
    page_content = fetch_page_with_selenium(driver, url)
    soup = BeautifulSoup(page_content, 'html.parser')

    summary = soup.find('div', class_='summary').text.strip() if soup.find('div', class_='summary') else "No summary available."
    duration = soup.find('li', class_='item-time').find('div', class_='content').text.strip() if soup.find('li', class_='item-time') else "No duration info."

    open_time = "No open time info."
    for dt in soup.find_all('dt'):
        if "开放时间" in dt.text:
            open_time = dt.find_next('dd').text.strip()
            break

    return {
        'name': spot_name,
        'summary': summary,
        'duration': duration,
        'open_time': open_time,
    }
# 进入“某一个景点详情页”，把这个景点的几个关键信息提取出来，最后把这些信息整理成一个字典返回。


def get_scenic_spots(driver, soup):
    spots = []
    spot_elements = soup.find_all('ul', class_='scenic-list clearfix')
    for spot in spot_elements[:1]:
        for item in spot.find_all('li'):
            name_node = item.find('h3')
            link_node = item.find('a', href=True)
            if not name_node or not link_node:
                continue
            spot_name = name_node.text.strip()
            spot_url = link_node['href']
            full_url = "https://www.mafengwo.cn" + spot_url if spot_url.startswith('/') else spot_url
            spot_details = get_scenic_spot_details(driver, full_url, spot_name)
            spots.append(spot_details)
            if len(spots) >= MAX_SCENIC_SPOTS:
                return spots
    return spots
# 从“目的地页面”里找出景点列表，拿到每个景点的名称和链接，
# 再逐个进入景点详情页抓取详细信息，最后把所有景点信息组成一个列表返回。

# get_scenic_spot_details：处理“一个景点”的详情
# get_scenic_spots：处理“多个景点”的列表，并调用前者拿每个景点的详情

def _pick_destination_url_from_search(soup):
    # 策略一：优先从搜索结果页里，找到“官方的目的地卡片链接”，再从这个链接里提取目的地id，拼出标准攻略页地址。
    mdd_anchor = soup.select_one("div.search-mdd-wrap a[href]")
    if mdd_anchor:
        href = mdd_anchor.get('href', '')#从 a 标签中取 href 属性。
        if href.startswith('//'):
            href = 'https:' + href
        elif href.startswith('/'):
            href = 'https://www.mafengwo.cn' + href

        try:
            parsed = urlparse(href) # 把一个长网址拆成几部分（协议、域名、路径、参数等）
            query = parse_qs(parsed.query) # 专门提取网址里 ? 后面的参数。
            mddid = (query.get('id') or [''])[0]
            share_type = (query.get('type') or [''])[0]
            if mddid and share_type == '10':
                return f'https://www.mafengwo.cn/jd/{mddid}/gonglve.html'
        except Exception:
            pass

    # 策略二：直达目的地详情页面的链接
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        if not href:
            continue
        if href.startswith('//'):
            href = 'https:' + href
        elif href.startswith('/'):
            href = 'https://www.mafengwo.cn' + href

        if ('/travel-scenic-spot/mafengwo/' in href) or ('/jd/' in href and href.endswith('/gonglve.html')):
            return href

    return None
# 从“马蜂窝搜索结果页”里，找出真正对应这个目的地的详情页链接，并返回这个链接。
# 如果找不到，就返回 None。
# 它的核心任务不是抓景点，而是先解决一个前置问题：
# “用户搜索了一个地名后，搜索结果页里真正应该进入哪个目的地页面？”


# 前面所有函数都为最后暴露出来的工具函数服务
@tool
def get_attractions_information(
    destination: Annotated[str, "目的地名称，必须是一个明确的城市或村镇名称"]
) -> dict:
    """景点搜索工具。获取目的地概览和景点信息列表。"""

    _ = load_dotenv(find_dotenv())
    driver = InitWebDriver()
    try:
        search_url = f"https://www.mafengwo.cn/search/q.php?q={destination}"
        print('search_url:', search_url)

        search_html = fetch_page_with_selenium(driver, search_url)
        search_soup = BeautifulSoup(search_html, 'html.parser')
        destination_url = _pick_destination_url_from_search(search_soup)

        if not destination_url:
            page_title = getattr(driver, 'title', '')
            current_url = getattr(driver, 'current_url', search_url)
            print(f"[warn] destination link not found. destination={destination}, url={current_url}, title={page_title}")
            return {
                'overview': f'未找到“{destination}”的目的地入口页面（网页结构可能变化）。',
                'scenic_list': [],
            }

        print('destination_url:', destination_url)
        destination_page = fetch_page_with_selenium(driver, destination_url)
        destination_soup = BeautifulSoup(destination_page, 'html.parser')

        overview = get_destination_overview(destination_soup)
        scenic_spots = get_scenic_spots(driver, destination_soup)

        return {
            'overview': overview,
            'scenic_list': scenic_spots,
        }
    finally:
        driver.quit()


if __name__ == '__main__':
    print(get_attractions_information.args_schema.model_json_schema())
    print(get_attractions_information.invoke({'destination': '福州'}))
