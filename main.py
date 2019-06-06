# -*- coding: utf-8 -*-
import asyncio
import aiohttp
import os

import requests
from lxml import html

from settings import BASE_URL, BOOKS_DIR

result = []
total_books_saved = 0


def get_genres():
    # return genre list links
    response = requests.get(BASE_URL)
    root = html.fromstring(response.content)
    links = root.xpath("//div[@id='menu_2']//a/@href")
    genres = {}

    for link in links:
        # link -> 'http://----.--/genre/khymerna/books/'
        genre_name = link.split('genre/')[1].split('/')[0]
        genres.update({
            genre_name: link,
        })

    return genres


def get_item(page_content, url):
    document = html.fromstring(page_content)

    links = document.xpath("//table[@class='books']//a/@href")
    try:
        genre = document.xpath(
            "//table[@class='books']//a[contains(@href, 'genre')]//text()"
        )[0]
    except IndexError:
        genre = 'unknown'

    if not links:
        print(url, 'No files')

    if not genre:
        genre = 'unknown'

    for extension in ('.fb2', '.djvu', '.txt', '.doc'):
        for link in links:
            if extension in link:
                return genre, link

    print('No files', url)
    return None, None


async def save_book(url, session):
    global total_books_saved
    async with session.get(url) as response:
        # Wait to response and block task
        page_content = await response.read()

        # get genre and book file link
        genre, link = get_item(page_content, url)

        if link:
            filename = link.split('/').pop()
            file_dir = os.path.join(BOOKS_DIR, genre)

            if not os.path.isdir(file_dir):
                os.mkdir(file_dir, 0o755)

            file_path = os.path.join(file_dir, filename)

            # skip if the book exists
            if not os.path.isfile(file_path):
                async with session.get(link) as resp2:
                    obj = await resp2.read()
                    with open(file_path, "wb") as f:
                        f.write(obj)

            total_books_saved += 1
            print(f'-- saved - {total_books_saved}')


async def walk_page(url, session):
    """ Get all urls referring to book page """
    async with session.get(url) as response:
        root = html.fromstring(await response.read())
        book_url_list = root.xpath("//table[@class='books']/tr/td/a[1]/@href")
        for i, url in enumerate(book_url_list):
            await save_book(url, session)


async def walk_pagination(url, session):
    """ Walk at pages from pagination.  """
    async with session.get(url) as response:
        root = html.fromstring(await response.read())
        try:
            last_page = int(
                root.xpath("//div[@class='paging']//a[last()]")[0].text
            )
        except (IndexError, AttributeError, ValueError):
            # One page only. Paginator not detected
            last_page = 1
        for i in range(last_page):
            page = f'{url}page-{i+1}/'
            await walk_page(page, session)


async def main():
    tasks = []
    genres = get_genres()
    async with aiohttp.ClientSession() as session:
        for genre, url in genres.items():
            task = asyncio.create_task(walk_pagination(url, session))
            tasks.append(task)

        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
