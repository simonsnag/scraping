import urllib.parse
import imdb_helper_functions as hf
import os
from bs4 import BeautifulSoup

URL = "https://imdb.com"
MOVIE_FILTERS = [
    "TV Series",
    "Short",
    "TV Episode",
    "TV Mini Series",
    "TV Movie",
    "TV Special",
    "TV Short",
    "Video Game",
    "Video",
    "Music Video",
    "Podcast Series",
    "Podcast Episode",
    "(voice)",
]


def get_actors_by_movie_soup(
    cast_page_soup, num_of_actors_limit=None, log_handler=False
):
    logger = hf._conf_logging(log_handler)
    actors_dict = {}

    try:
        cast_list = cast_page_soup.find_all("table", {"class": "cast_list"})
        if not cast_list:
            logger.info("No cast list found")
            return actors_dict

        logger.info("Cast tag was found")
        actors = cast_list[0].find_all("tr")
        logger.info("Start processing actors")
        for actor in actors:
            columns = actor.find_all("td")
            if len(columns) > 1:
                actor_name = "_".join(columns[1].text.split())
                rel_link = "/".join(columns[1].find("a")["href"].split("/")[:-1])
                actor_url = urllib.parse.urljoin(URL, rel_link)
                actor_id = actor_url.split("/")[-1]
                actors_dict[actor_id] = (actor_name, actor_url)
                if num_of_actors_limit and len(actors_dict) >= num_of_actors_limit:
                    logger.info("Actors were successfully added to the dict")
                    break
        logger.info("Actors were successfully added to the dict")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    return actors_dict


def get_movies_by_actor_soup(
    actor_page_soup, num_of_movies_limit=None, log_handler=False
):
    logger = hf._conf_logging(log_handler)
    movies_dict = {}

    try:
        filmography = actor_page_soup.find(
            "div", {"id": "accordion-item-actor-previous-projects"}
        )
        if not filmography:
            filmography = actor_page_soup.find(
                "div", {"id": "accordion-item-actress-previous-projects"}
            )

        if not filmography:
            logger.info("Filmography not found")
            return movies_dict

        logger.info("Filmography was found")
        ul = filmography.find("div", recursive=False).find("ul", recursive=False)
        if not ul:
            logger.info("No movie list found")
            return movies_dict

        movies = ul.find_all("li", recursive=False)
        logger.info("Start processing movies")

        for movie in movies:
            # This part filtered movies, and processed only featured
            spans = movie.find_all("span")
            if any(
                filter_keyword.lower() in span.text.lower()
                for span in spans
                for filter_keyword in MOVIE_FILTERS
            ):
                continue
            a_tag = (
                movie.find_all("div", recursive=False)[1]
                .find("div", recursive=False)
                .find("a", recursive=False)
            )
            movie_name = "_".join(a_tag.text.split())
            rel_link = "/".join(a_tag["href"].split("/")[:-1])
            movie_link = urllib.parse.urljoin(URL, rel_link)
            movie_id = movie_link.split("/")[-1]
            movies_dict[movie_id] = (movie_name, movie_link)
            if num_of_movies_limit and len(movies_dict) >= num_of_movies_limit:
                logger.info("Movies were successfully added to the list")
                break
        logger.info("Movies were successfully added to the list")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise

    return movies_dict


def get_movie_distance(
    actor_start_url,
    actor_end_url,
    num_of_actors_limit=None,
    num_of_movies_limit=None,
    log_handler=False,
):
    logger = hf._conf_logging(log_handler)

    # Tracking visited movies and actors
    seen_movies = set()
    seen_actors = set()
    current_distance = 1

    # Main dictionary with co-actors by levels
    actor_start_co = {}
    actor_start_co[f"co_actors_level_{current_distance}"] = hf.find_co_actors(
        actor_start_url,
        seen_movies,
        seen_actors,
        num_of_actors_limit,
        num_of_movies_limit,
        log_handler,
    )

    # Main loop
    while current_distance <= 10:
        cur_lvl = f"co_actors_level_{current_distance}"
        prev_lvl = f"co_actors_level_{current_distance - 1}"

        if current_distance == 1:
            logger.info("Checking first level")
            for actor_id in actor_start_co[cur_lvl]:
                if actor_id == actor_end_url.split("/")[-1]:
                    return current_distance
        else:
            logger.info(f"Checking level number {current_distance}")

            seen_movies_2, seen_actors_2 = set(), set()
            actor_end_co = hf.find_co_actors(
                actor_end_url,
                seen_movies_2,
                seen_actors_2,
                num_of_actors_limit,
                num_of_movies_limit,
                log_handler,
            )

            inter_actor = actor_start_co[prev_lvl].intersection(actor_end_co)
            if inter_actor:
                logger.info(
                    f"Amount of intermediate actors by level #{current_distance}: {len(inter_actor)}"
                )
                return current_distance
            else:
                logger.info("Adding actors in level {current_distance}")
                for actor_id in actor_start_co[prev_lvl]:
                    actor_url = "https://imdb.com/name/" + actor_id
                    co_actors = hf.find_co_actors(
                        actor_url,
                        seen_movies,
                        seen_actors,
                        num_of_actors_limit,
                        num_of_movies_limit,
                        log_handler,
                    )
                    actor_start_co.setdefault(cur_lvl, set()).update(co_actors)

        current_distance += 1

    logger.info(f"No connection found between {actor_start_url} and {actor_end_url}")
    return None


def get_movie_descriptions_by_actor_soup(
    actor_page_soup, actor_name, log_handler=False
):
    logger = hf._conf_logging(log_handler)

    movies = get_movies_by_actor_soup(actor_page_soup)
    all_descriptions = ""

    logger.info("Start proccessing movie")
    for movie in movies.values():
        soup = hf.dl_cast_page_soup(movie[1])
        description = hf.get_short_description(soup, log_handler)
        all_descriptions += f"{description} \n"

    # Saving descriptions
    directory = "actors_movie_description"
    filename = actor_name + ".txt"
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info("Directory was created.")

    filepath = os.path.join(directory, filename)

    with open(filepath, "w") as f:
        f.write(all_descriptions)
        logger.info(f"Descriptions saved for {actor_name}")

    return all_descriptions
