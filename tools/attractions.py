import logging
import time
from typing import Annotated
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup
from dotenv import find_dotenv, load_dotenv
from langchain_core.tools import tool
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.remote_connection import LOGGER
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from tools.base import fail, get_tool_logger, ok

MAX_SCENIC_SPOTS = 5


def InitWebDriver():
    LOGGER.setLevel(logging.WARNING)
    options = webdriver.ChromeOptions()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(12)
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


def fetch_page_with_selenium(driver, url):
    driver.get(url)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(1)
    return driver.page_source


def get_destination_overview(soup):
    overview_element = soup.find("span", {"id": "mdd_poi_desc"})
    if overview_element:
        return overview_element.text.strip()
    return "Overview not found."


def get_scenic_spot_details(driver, url, spot_name):
    page_content = fetch_page_with_selenium(driver, url)
    soup = BeautifulSoup(page_content, "html.parser")

    summary_node = soup.find("div", class_="summary")
    summary = summary_node.text.strip() if summary_node else "No summary available."

    duration = "No duration info."
    duration_node = soup.find("li", class_="item-time")
    if duration_node:
        duration_content = duration_node.find("div", class_="content")
        if duration_content:
            duration = duration_content.text.strip()

    open_time = "No open time info."
    for dt in soup.find_all("dt"):
        if "开放时间" in dt.text:
            open_time_node = dt.find_next("dd")
            if open_time_node:
                open_time = open_time_node.text.strip()
            break

    return {
        "name": spot_name,
        "summary": summary,
        "duration": duration,
        "open_time": open_time,
    }


def get_scenic_spots(driver, soup):
    spots = []
    spot_elements = soup.find_all("ul", class_="scenic-list clearfix")
    for spot in spot_elements[:1]:
        for item in spot.find_all("li"):
            name_node = item.find("h3")
            link_node = item.find("a", href=True)
            if not name_node or not link_node:
                continue
            spot_name = name_node.text.strip()
            spot_url = link_node["href"]
            full_url = "https://www.mafengwo.cn" + spot_url if spot_url.startswith("/") else spot_url
            spot_details = get_scenic_spot_details(driver, full_url, spot_name)
            spots.append(spot_details)
            if len(spots) >= MAX_SCENIC_SPOTS:
                return spots
    return spots


def _pick_destination_url_from_search(soup):
    mdd_anchor = soup.select_one("div.search-mdd-wrap a[href]")
    if mdd_anchor:
        href = mdd_anchor.get("href", "")
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = "https://www.mafengwo.cn" + href

        try:
            parsed = urlparse(href)
            query = parse_qs(parsed.query)
            mddid = (query.get("id") or [""])[0]
            share_type = (query.get("type") or [""])[0]
            if mddid and share_type == "10":
                return f"https://www.mafengwo.cn/jd/{mddid}/gonglve.html"
        except Exception:
            pass

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not href:
            continue
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = "https://www.mafengwo.cn" + href

        if ("/travel-scenic-spot/mafengwo/" in href) or ("/jd/" in href and href.endswith("/gonglve.html")):
            return href

    return None


def _fallback_with_web_search(destination: str, reason: str) -> dict:
    from tools.web_search import web_search

    search_result = web_search.invoke({
        "keywords": f"{destination} 景点 推荐 旅游",
        "max_results": 5,
    })
    if not search_result.get("success"):
        return fail(
            "attractions_fallback_failed",
            {
                "selenium_error": reason,
                "fallback_error": search_result.get("error"),
            },
            retryable=bool(search_result.get("error", {}).get("retryable")),
        )

    results = search_result["data"].get("results", [])
    scenic_list = []
    for item in results[:MAX_SCENIC_SPOTS]:
        scenic_list.append({
            "name": item.get("title", "")[:60],
            "summary": item.get("body", ""),
            "duration": "No duration info.",
            "open_time": "No open time info.",
            "url": item.get("href", ""),
        })

    return ok({
        "source": "web_search_fallback",
        "fallback_used": True,
        "warnings": [f"Selenium 景点抓取失败，已降级使用网页搜索。原因摘要：{reason}"],
        "overview": f"因景点页面抓取失败，已使用网页搜索结果为“{destination}”生成候选景点信息。",
        "scenic_list": scenic_list,
    })


@tool
def get_attractions_information(
    destination: Annotated[str, "目的地名称，必须是一个明确的城市或村镇名称"]
) -> dict:
    """景点搜索工具。获取目的地概览和景点信息列表。"""

    _ = load_dotenv(find_dotenv())
    logger = get_tool_logger("get_attractions_information")
    started_at = time.perf_counter()
    driver = None

    try:
        driver = InitWebDriver()
        search_url = f"https://www.mafengwo.cn/search/q.php?q={destination}"

        search_html = fetch_page_with_selenium(driver, search_url)
        search_soup = BeautifulSoup(search_html, "html.parser")
        destination_url = _pick_destination_url_from_search(search_soup)

        if not destination_url:
            reason = "未找到目的地入口页面，网页结构可能变化。"
            logger.warning(
                "tool=get_attractions_information status=fallback destination=%s reason=%s",
                destination,
                reason,
            )
            return _fallback_with_web_search(destination, reason)

        destination_page = fetch_page_with_selenium(driver, destination_url)
        destination_soup = BeautifulSoup(destination_page, "html.parser")

        overview = get_destination_overview(destination_soup)
        scenic_spots = get_scenic_spots(driver, destination_soup)

        if not scenic_spots:
            reason = "目的地页面未解析到景点列表，网页结构可能变化。"
            logger.warning(
                "tool=get_attractions_information status=fallback destination=%s reason=%s",
                destination,
                reason,
            )
            return _fallback_with_web_search(destination, reason)

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "tool=get_attractions_information status=success destination=%s scenic_count=%s elapsed_ms=%s",
            destination,
            len(scenic_spots),
            elapsed_ms,
        )
        return ok({
            "source": "mafengwo",
            "fallback_used": False,
            "warnings": [],
            "overview": overview,
            "scenic_list": scenic_spots,
        })
    except (TimeoutException, WebDriverException) as exc:
        reason = f"{exc.__class__.__name__}: {str(exc)[:160]}"
        logger.warning(
            "tool=get_attractions_information status=fallback destination=%s reason=%s",
            destination,
            reason,
        )
        return _fallback_with_web_search(destination, reason)
    finally:
        if driver is not None:
            try:
                driver.quit()
            except WebDriverException:
                logger.warning(
                    "tool=get_attractions_information status=driver_quit_failed destination=%s",
                    destination,
                )


if __name__ == "__main__":
    print(get_attractions_information.args_schema.model_json_schema())
    print(get_attractions_information.invoke({"destination": "福州"}))
