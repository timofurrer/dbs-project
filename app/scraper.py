"""
Scraper for digitec/galaxus live feed.
"""

import re
import logging
import asyncio
import itertools
from urllib.parse import urlparse
from typing import List, Dict

import maya
import aiohttp
from bs4 import BeautifulSoup

import rethinkdb as r
r.set_loop_type("asyncio")

from models import TransactionType, Transaction

URLS = [
    'http://digitec.ch/de/SocialShopping/GetFeedData/1',
    'http://galaxus.ch/de/SocialShopping/GetFeedData/1'
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36",
    "accept-encoding": "gzip, deflate, sdch, br",
    "x-requested-with": "XMLHttpRequest",
    "accept-language": "de-DE,de;q=0.8,en-US;q=0.6,en;q=0.4",
    "accept": "*/*",
    "referer": "https://www.digitec.ch/de/wiki/2736",
    "authority": "www.digitec.ch"
}

GET_PARAMS = {
        "minTransactionTime": "2018-05-16T20:38:00",  # NOTE(TF): doesn't seem to affect the result at all
    "languageId": 2,
    "_": 42  # NOTE(TF): what is this field?!
}


#: Holds the logger for scraping
logger = logging.getLogger('scraper')
logging.basicConfig(level=logging.INFO)


class Scraper:
    """
    Async Digitec/Galaxus live feed scraper.

    Arguments:
        feed_urls (list) -- URLs to live feeds
    """
    def __init__(self, transaction_queue: asyncio.Queue, feed_urls: List[str]) -> None:
        self.transaction_queue = transaction_queue
        self.feed_urls = feed_urls

    async def scrape(self, headers: Dict[str, str], params: Dict[str, object]):
        """
        Start scraping on the initialized URLs.
        """
        while True:  # fuck yeah!
            async with aiohttp.ClientSession(headers=headers) as session:
                # fetch feed URLs
                responses = await asyncio.gather(*[loop.create_task(
                    self._fetch(session, url, params)) for url in self.feed_urls])

                # aggregate feed URLs and parsed responses
                transactions = itertools.chain(*[list(
                    zip(itertools.repeat(u), t))
                    for u, t in zip(self.feed_urls, map(self._parse, responses))])

                # add transactions to queue
                for transaction in transactions:
                    await self.transaction_queue.put(transaction)
            await asyncio.sleep(15)

    def _parse(self, response: str) -> List[Transaction]:
        """

        """
        soup = BeautifulSoup(response, "html.parser")
        raw_transactions = soup.find_all("div")
        logger.info("Scraped %d transations", len(raw_transactions))
        transactions = []

        for raw_transaction in raw_transactions:
            def __extract_attribute(attr):
                val = raw_transaction.find_all("span", {"class": attr})
                return val[0].get_text().strip() if val else None

            try:
                # wrangle a bit
                full_trans = raw_transaction.get_text()
                full_trans = re.sub(" +", " ", full_trans)
                full_trans = re.sub("\n", "", full_trans)

                # parse response content attributes
                timestamp = maya.parse(
                        raw_transaction.get("data-transaction-time")).rfc2822()
                brand = __extract_attribute("brand")
                product = __extract_attribute("product")
                price = __extract_attribute("price")
                location = re.search("from(?: our store in)? (.*?)( just | is | rated |$)", full_trans)
                location = location.group(1).strip() if location else None
                customer = re.search("((?:[0-9][0-9]:[0-9][0-9]\xa0)|to )([^\s]*?) (from|is collecting|is answering)", full_trans)
                customer = customer.group(2).strip() if customer else None

                transaction_type = TransactionType.identify(full_trans)

                # some arbitrary text
                text = None
                if transaction_type == TransactionType.RATED:
                    text = re.search(r"with (.*?)$", full_trans).group(1)
                elif transaction_type == TransactionType.SEARCH:
                    text = re.search("( is looking for )(.*)", full_trans)
                    text = text.group(2).strip() if text else None
                elif transaction_type == TransactionType.ANSWERING:
                    text = re.search(r"is answering (.*)", full_trans).group(1)

                transaction = Transaction(
                        transaction_type,
                        timestamp, customer, location,
                        brand, product, price, text)

                logger.debug("Got transaction %r", transaction)
                logger.info("FULL TRANS %s", full_trans)
                transactions.append(transaction)
            except Exception as exc:
                logger.error("Unable to parse transaction: '%s': %s", full_trans, str(exc))

        return transactions

    async def _fetch(self, session, url: str, params: Dict[str, object]):
        async with session.get(url, params=params) as response:
            return await response.text()


class Persister:
    def __init__(self, transaction_queue):
        self.transaction_queue = transaction_queue

    async def consume(self):
        """
        Consume transactions and import to database
        """
        connection = await r.connect("db", 28015)
        try:
            await r.db("test").table_create("transactions").run(connection)
        except:
            pass

        try:
            await r.db("test").table_create("products").run(connection)
        except:
            pass

        try:
            await r.db("test").table_create("suppliers").run(connection)
        except:
            pass

        await asyncio.sleep(1)

        while True:
            transaction = await self.transaction_queue.get()
            if transaction is None:
                # producer is done
                break

            try:
                async def __expand_cursor(c):
                    records = []
                    while (await c.fetch_next()):
                        records.append(await c.next())
                    return records

                supplier_document_id = urlparse(transaction[0]).netloc
                supplier_document = {
                    "id": supplier_document_id
                }

                existing_supplier_document = await r.table("suppliers").get(
                        supplier_document_id).run(connection)

                if not existing_supplier_document:
                    await r.table("suppliers").insert(supplier_document).run(connection)
                    logger.info("Inserting new Supplier %s", supplier_document_id)

                product_document = {
                    "name": str(transaction[1].product),
                    "brand": str(transaction[1].brand),
                    "price": str(transaction[1].price)
                }

                existing_product_document = await r.table("products").filter(
                        product_document).pluck("id").run(connection)
                existing_product_document = await __expand_cursor(existing_product_document)

                if not existing_product_document:
                    product_document_insert = await r.table("products").insert(
                            product_document).run(connection)
                    product_document_id = product_document_insert["generated_keys"][0]
                    logger.info("Inserting new Product %s", product_document)
                else:
                    product_document_id = existing_product_document[0]["id"]

                transaction_document = {
                    "type": str(transaction[1].transaction_type),
                    "timestamp": str(transaction[1].timestamp),
                    "location": str(transaction[1].location),
                    "customer": str(transaction[1].customer),
                    "product_id": product_document_id,
                    "supplier_id": supplier_document_id,
                }

                if transaction[1].text is not None:
                    transaction_document["text"] = str(transaction[1].text)

                # only insert the transaction if it does not exist yet
                existing_transaction_document = await r.table("transactions").filter(
                        transaction_document).limit(1).run(connection)
                existing_transaction_document = await __expand_cursor(existing_transaction_document)
                if not existing_transaction_document:
                    logger.info("Inserting new Transaction %s", transaction_document)
                    await r.table("transactions").insert(transaction_document).run(connection)
            except Exception as exc:
                logger.error("Failed to insert Transaction %s because of %s", str(transaction), str(exc))


if __name__ == "__main__":
    queue = asyncio.Queue()
    s = Scraper(queue, URLS)
    p = Persister(queue)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(p.consume(), s.scrape(HEADERS, GET_PARAMS)))
