"""
Selenium end-to-end test for the Yield Monitor dashboard.

Inserts 5 tests for part 001PN001 (3 pass, 2 fail), clicks the pie slice,
and asserts the yield gauge shows 60%.

Usage:
    BASE_URL=http://localhost:8000 python test_yield.py
"""
import os
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
EXPECTED_YIELD = 60.0
PART_NUMBER = "001PN001"

# 5 records: 3 pass, 2 fail = 60% yield
RECORDS = [
    ("SN-TEST-001", True),
    ("SN-TEST-002", True),
    ("SN-TEST-003", True),
    ("SN-TEST-004", False),
    ("SN-TEST-005", False),
]


def build_driver() -> webdriver.Chrome:
    opts = Options()
    if os.getenv("HEADLESS", "1") == "1":
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1400,900")
    return webdriver.Chrome(options=opts)


def submit_record(driver: webdriver.Chrome, wait: WebDriverWait, serial: str, status: bool) -> None:
    wait.until(EC.element_to_be_clickable((By.ID, "manualTestBtn"))).click()
    sn = wait.until(EC.visibility_of_element_located((By.ID, "serialNumber")))
    sn.clear()
    sn.send_keys(serial)

    Select(driver.find_element(By.ID, "partNumber")).select_by_value(PART_NUMBER)

    checkbox = driver.find_element(By.ID, "status")
    if checkbox.is_selected() != status:
        checkbox.click()

    driver.find_element(By.ID, "addBtn").click()
    # Wait for the modal to close (form submit handler hides it on success).
    wait.until(EC.invisibility_of_element_located((By.ID, "serialNumber")))


def click_pie_slice_for_part(driver: webdriver.Chrome, part_number: str) -> None:
    # Use the legend row as a deterministic click target — it triggers the same
    # selectedPart update path as clicking the pie slice itself.
    row = driver.find_element(By.CSS_SELECTOR, f'.legend-row[data-part="{part_number}"]')
    row.click()


def read_gauge_pct(driver: webdriver.Chrome) -> float:
    text = driver.find_element(By.ID, "gaugePct").text.strip()
    if text.endswith("%"):
        text = text[:-1]
    return float(text)


def main() -> int:
    driver = build_driver()
    wait = WebDriverWait(driver, 15)
    try:
        driver.get(BASE_URL)
        wait.until(EC.element_to_be_clickable((By.ID, "manualTestBtn")))

        for serial, status in RECORDS:
            submit_record(driver, wait, serial, status)
            time.sleep(0.2)

        # Give the dashboard a moment to refresh charts after the last insert.
        time.sleep(1.0)
        click_pie_slice_for_part(driver, PART_NUMBER)
        time.sleep(0.3)

        actual = read_gauge_pct(driver)
        if abs(actual - EXPECTED_YIELD) < 0.05:
            print(f"PASS: yield={actual}% (expected {EXPECTED_YIELD}%)")
            return 0
        print(f"FAIL: yield={actual}% (expected {EXPECTED_YIELD}%)")
        return 1
    finally:
        driver.quit()


if __name__ == "__main__":
    sys.exit(main())
