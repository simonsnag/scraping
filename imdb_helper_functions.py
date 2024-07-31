import logging
import time
import imdb_code as mf
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException,
)
from bs4 import BeautifulSoup
import shelve
import re


def _conf_logging(log_handler=False):
    logger = logging.getLogger(__name__)
    if log_handler:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.CRITICAL)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def _get_driver():
    # Settings for selenium driver
    chrome_options = Options()
    chrome_prefs = {
        "intl.accept_languages": "en-US,en",
        "profile.default_content_setting_values": {"automatic_downloads": 1},
    }
    chrome_options.add_experimental_option("prefs", chrome_prefs)
    chrome_options.add_argument("--lang=en-US")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("start-maximized")
    driver = webdriver.Chrome(options=chrome_options)
    return driver


def clear_cache(driver):
    # Clearing cache in the browser
    driver.execute_script("window.localStorage.clear();")
    driver.execute_script("window.sessionStorage.clear();")
    driver.execute_script(
        "caches.keys().then(function(names) { for (let name of names) caches.delete(name); });"
    )


def dl_cast_page_soup(url, log_handler=False, save_handler=False):
    logger = _conf_logging(log_handler)
    driver = _get_driver()

    try:
        driver.get(url)
        html = driver.page_source
        logger.info("Page loaded successfully")
        if save_handler:
            # This part for saving in case it would be a lot of pages to load
            name = url.split("/")[-1] + ".html"
            with open(name, "w", encoding="utf-8") as f:
                f.write(html)
                logger.info("Page was saved")
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        if logging:
            logger.error(f"An error occurred: {e}")
    finally:
        driver.delete_all_cookies()
        driver.quit()
    return soup


def dl_actor_page_soup(url, log_handler=False, save_handler=False):
    logger = _conf_logging(log_handler)
    driver = _get_driver()

    try:
        driver.get(url)
        xpath = '//*[@data-testid="Filmography"]/section/div/button'

        try:
            expand_below_button = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            driver.execute_script(
                "arguments[0].scrollIntoView(true);", expand_below_button
            )
            time.sleep(1)

            actions = ActionChains(driver)
            actions.move_to_element(expand_below_button).click().perform()
            time.sleep(5)

            logger.info("Expand below button was found and clicked")
        except (ElementClickInterceptedException, TimeoutException):
            logger.warning("Fail to click button")

        html = driver.page_source
        logger.info("Page loaded successfully")

        if save_handler:
            name = url.split("/")[-1] + ".html"
            with open(name, "w", encoding="utf-8") as f:
                f.write(html)
                logger.info("Page was saved")

        soup = BeautifulSoup(html, "html.parser")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        soup = None

    finally:
        clear_cache(driver)
        driver.delete_all_cookies()
        driver.quit()

    return soup


def find_co_actors(
    actor_url,
    seen_movies,
    seen_actors,
    num_of_actors_limit=None,
    num_of_movies_limit=None,
    log_handler=False,
):
    logger = _conf_logging(log_handler)
    cache = DataCache()

    actor_id = actor_url.split("/")[-1]
    movies = cache.load_data(f"movies_by_{actor_id}")

    if not movies:
        actor_page_soup = dl_actor_page_soup(actor_url, log_handler=log_handler)
        movies = mf.get_movies_by_actor_soup(
            actor_page_soup,
            num_of_movies_limit=num_of_movies_limit,
            log_handler=log_handler,
        )
        cache.save_data(f"movies_by_{actor_id}", movies)
        logger.info(f"{len(movies)} were saved by actor {actor_id}")

    new_movies = set([movie_id for movie_id in movies if movie_id not in seen_movies])
    seen_movies.update(new_movies)
    logger.info(f"Amount of seen movies {len(seen_movies)}")

    actors = set()
    for movie_id in new_movies:
        movie_actors = cache.load_data(f"actors_by_{movie_id}")

        if not movie_actors:
            movie_url = "https://imdb.com/title/" + movie_id + "/fullcredits"
            movie_page_soup = dl_cast_page_soup(movie_url, log_handler=log_handler)
            movie_actors = mf.get_actors_by_movie_soup(
                movie_page_soup,
                num_of_actors_limit=num_of_actors_limit,
                log_handler=log_handler,
            )
            cache.save_data(f"actors_by_{movie_id}", movie_actors)

        new_actors = set(
            [
                act_id
                for act_id in movie_actors
                if act_id not in seen_actors and act_id != actor_id
            ]
        )
        seen_actors.update(new_actors)
        actors.update(new_actors)

    logger.info(f"Amount of actors in this level {len(actors)}")

    return actors


def get_short_description(movie_page_soup, log_handler=False):
    logger = _conf_logging(log_handler)
    
    try:
        pattern = re.compile("ipc-page-section ipc-page-section--baseAlt ipc-page-section--tp-none ipc-page-section--bp-xs.*")
        section = movie_page_soup.find('section', class_=pattern)
        if not section:
            logger.warning('Section tag was not found')
        spans = section.find('p').find_all('span')
        if not spans:
            logger.warning('Description tag was not found')

        description = spans[2].text
        logger.info('Description was found')
        return description
    except Exception as e:
        logger.error(f"An error occurred: {e}")

class DataCache:
    def __init__(self, filename="data_cache"):
        self.filename = filename

    def save_data(self, key, data):
        with shelve.open(self.filename) as db:
            db[key] = data
            print(f"Data saved for key: {key}")

    def load_data(self, key):
        with shelve.open(self.filename) as db:
            data = db.get(key, None)
            return data
