from pathlib import Path
from playwright.sync_api import sync_playwright

DETAIL_URL = "https://down.foodmate.net/standard/sort/3/108497.html"
OUT_PNG = r"screenshot\gb_2763-2021_head_table.png"

def clamp(v, lo=0):
    return max(lo, v)

Path(OUT_PNG).parent.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        viewport={"width": 1400, "height": 900},
        device_scale_factor=1,
    )

    page.goto(DETAIL_URL, wait_until="domcontentloaded", timeout=120000)
    page.evaluate("window.scrollTo(0, 0)")

    fl_rb = page.locator("div.fl_rb").first
    title = page.locator("div.fl_rb div.title2").first
    table = page.locator("div.fl_rb table.xztable").first

    title.wait_for(state="visible", timeout=30000)
    table.wait_for(state="visible", timeout=30000)

    b_fl = fl_rb.bounding_box()
    b_t = title.bounding_box()
    b_tb = table.bounding_box()
    assert b_fl and b_t and b_tb

    pad = 8
    left = clamp(b_fl["x"] - pad)
    top = clamp(b_t["y"] - pad)
    right = b_fl["x"] + b_fl["width"] + pad
    bottom = b_tb["y"] + b_tb["height"] + pad

    clip = {"x": left, "y": top, "width": right - left, "height": bottom - top}
    page.screenshot(path=OUT_PNG, clip=clip)

    browser.close()

print("saved:", OUT_PNG)