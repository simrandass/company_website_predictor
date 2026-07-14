# scraper.py
import os
import time
import random
import logging
import re
import json
from typing import Optional, Dict
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import chromedriver_autoinstaller

# ---------- Global configuration ----------
_SERPER_API_KEY = os.getenv('SERPER_API_KEY', None)
_HEADLESS = True

def configure_scraper(serper_api_key: str = None, headless: bool = True):
    """Set global configuration for the scraper."""
    global _SERPER_API_KEY, _HEADLESS
    if serper_api_key:
        _SERPER_API_KEY = serper_api_key
    _HEADLESS = headless

# ---------- Logging ----------
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class LinkedInScraper:
    # ... (same as before – no changes needed inside the class) ...
    # I'll include the full class for completeness, but it's identical to the previous version.
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None

    def _create_driver(self):
        chromedriver_autoinstaller.install()
        options = Options()
        if self.headless:
            options.add_argument('--headless=new')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1200,800')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.chrome = { runtime: {} };
            """
        })
        return driver

    def _ensure_driver(self):
        try:
            if self.driver is None:
                self.driver = self._create_driver()
            else:
                self.driver.current_url
        except (WebDriverException, Exception):
            try:
                self.driver.quit()
            except:
                pass
            self.driver = self._create_driver()

    def cleanup_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

    def _is_valid_company_website(self, domain: str) -> bool:
        if not domain:
            return False
        blacklist = ['linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com',
                     'youtube.com', 'wikipedia.org', 'glassdoor.com', 'indeed.com',
                     'crunchbase.com', 'bloomberg.com', 'reuters.com', 'static.licdn.com']
        domain = domain.lower()
        for b in blacklist:
            if b in domain:
                return False
        if '.' not in domain:
            return False
        valid_tlds = ['.com', '.org', '.net', '.io', '.co', '.uk', '.de', '.fr',
                      '.cn', '.jp', '.in', '.ai']
        return any(domain.endswith(tld) for tld in valid_tlds)

    def _clean_website_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        try:
            if 'linkedin.com/redir/' in url:
                m = re.search(r'url=([^&]+)', url)
                if m:
                    url = m.group(1)
            if '%' in url:
                try:
                    url = requests.utils.unquote(url)
                except:
                    pass
            parsed = urlparse(url)
            if not parsed.scheme:
                url = f"http://{url}"
                parsed = urlparse(url)
            domain = parsed.netloc
            if domain.startswith('www.'):
                domain = domain[4:]
            domain = domain.rstrip('/')
            if self._is_valid_company_website(domain):
                return domain
            return None
        except:
            return None

    def _extract_website_from_button(self):
        try:
            if not self.driver:
                return None
            selectors = [
                '.org-page-details__website-link',
                '.link-without-visited-state',
                '.org-top-card__website-link',
                'a[data-anonymize="company-website"]',
                'a[href*="linkedin.com/redir/"]'
            ]
            for sel in selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for elem in elements:
                    href = elem.get_attribute('href')
                    if href:
                        website = self._clean_website_url(href)
                        if website:
                            return website
            links = self.driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                text = link.text.strip().lower()
                if 'website' in text or 'site' in text:
                    href = link.get_attribute('href')
                    if href:
                        website = self._clean_website_url(href)
                        if website:
                            return website
            return None
        except:
            return None

    def _extract_website_from_text(self):
        try:
            if not self.driver:
                return None
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            patterns = [
                r'Website[:\s]*([a-zA-Z0-9-]+\.[a-zA-Z]{2,})',
                r'Visit our website[:\s]*([a-zA-Z0-9-]+\.[a-zA-Z]{2,})',
            ]
            for pat in patterns:
                m = re.search(pat, page_text, re.IGNORECASE)
                if m:
                    website = self._clean_website_url(m.group(1))
                    if website:
                        return website
            return None
        except:
            return None

    def _extract_website_from_description(self):
        try:
            desc = self._extract_description()
            if desc:
                url_pattern = r'(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.[a-zA-Z]{2,})'
                m = re.search(url_pattern, desc)
                if m:
                    website = self._clean_website_url(m.group(1))
                    if website:
                        return website
            return None
        except:
            return None

    def _extract_website_from_page_source(self):
        try:
            if not self.driver:
                return None
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            meta = soup.find('meta', {'name': 'website'})
            if meta and meta.get('content'):
                website = self._clean_website_url(meta.get('content'))
                if website:
                    return website
            return None
        except:
            return None

    def _extract_website_from_json_ld(self):
        try:
            if not self.driver:
                return None
            scripts = self.driver.find_elements(By.XPATH, "//script[@type='application/ld+json']")
            for script in scripts:
                try:
                    data = json.loads(script.get_attribute('innerHTML'))
                    if isinstance(data, dict):
                        if 'url' in data:
                            website = self._clean_website_url(data['url'])
                            if website:
                                return website
                        if 'sameAs' in data and isinstance(data['sameAs'], list):
                            for url in data['sameAs']:
                                website = self._clean_website_url(url)
                                if website and 'linkedin.com' not in website:
                                    return website
                except:
                    continue
            return None
        except:
            return None

    def _extract_company_name(self, profile_url):
        try:
            if 'linkedin.com/company/' in profile_url:
                name = profile_url.split('linkedin.com/company/')[-1].split('/')[0]
                return name.replace('-', ' ').title()
            title = self.driver.title if self.driver else ''
            if ' | LinkedIn' in title:
                return title.replace(' | LinkedIn', '').strip()
            return None
        except:
            return None

    def _extract_description(self):
        try:
            if not self.driver:
                return None
            selectors = ['.org-page-details__description-text', '.break-words', '.org-top-card__description']
            for sel in selectors:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    return el.text.strip()
                except:
                    continue
            return None
        except:
            return None

    def _extract_industry(self):
        try:
            if not self.driver:
                return None
            selectors = ['.org-page-details__industry', '.org-top-card__industry']
            for sel in selectors:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    return el.text.strip()
                except:
                    continue
            return None
        except:
            return None

    def scrape_linkedin_profile(self, profile_url: str, timeout: int = 20) -> Dict:
        result = {
            'website': None,
            'company_name': None,
            'description': None,
            'industry': None,
            'employee_count': None,
            'headquarters': None
        }
        try:
            self._ensure_driver()
            self.driver.set_page_load_timeout(timeout)
            self.driver.get(profile_url)
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(random.uniform(1.5, 3.5))
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

            website = (self._extract_website_from_button() or
                       self._extract_website_from_text() or
                       self._extract_website_from_description() or
                       self._extract_website_from_page_source() or
                       self._extract_website_from_json_ld())

            if website and website != 'static.licdn.com' and self._is_valid_company_website(website):
                result['website'] = website

            result['company_name'] = self._extract_company_name(profile_url)
            result['description'] = self._extract_description()
            result['industry'] = self._extract_industry()

        except TimeoutException:
            logger.warning(f"Timeout for {profile_url}")
        except WebDriverException as e:
            logger.warning(f"WebDriver error: {e}")
            self.driver = None
        except Exception as e:
            logger.warning(f"Unexpected error: {e}")
        return result

    def scrape_with_retry(self, profile_url: str, max_retries: int = 3) -> Dict:
        for attempt in range(max_retries):
            result = self.scrape_linkedin_profile(profile_url)
            if result.get('website'):
                return result
            if attempt < max_retries - 1:
                wait = (2 ** attempt) + random.uniform(0, 1)
                logger.info(f"Retry {attempt+1} in {wait:.1f}s")
                time.sleep(wait)
                self.cleanup_driver()
        return result

    def __del__(self):
        self.cleanup_driver()


# ---------- Helper ----------
def _get_linkedin_profile_url(company_name: str) -> Optional[str]:
    if _SERPER_API_KEY is None:
        raise ValueError("SERPER_API_KEY not set. Call configure_scraper() or set environment variable.")
    try:
        search_query = f"{company_name} LinkedIn"
        params = {'api_key': _SERPER_API_KEY, 'q': search_query, 'num': 5}
        response = requests.get('https://google.serper.dev/search', params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        for result in data.get('organic', []):
            link = result.get('link', '')
            if 'linkedin.com/company/' in link:
                return link
        return None
    except Exception as e:
        logger.warning(f"LinkedIn search failed: {e}")
        return None


# ---------- Exported function ----------
def get_linkedin_domain(company_name: str) -> Optional[str]:
    """
    Search for LinkedIn profile, scrape it, and return the website domain.
    Uses global SERPER_API_KEY (set via configure_scraper or environment variable).
    Returns None if not found or error.
    """
    linkedin_url = _get_linkedin_profile_url(company_name)
    if not linkedin_url:
        return None
    scraper = LinkedInScraper(headless=_HEADLESS)
    result = scraper.scrape_with_retry(linkedin_url)
    scraper.cleanup_driver()
    domain = result.get('website')
    if domain and domain != 'static.licdn.com':
        return domain
    return None