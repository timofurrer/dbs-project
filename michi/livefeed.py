import signal
import sys
import re
import time
import requests
import threading
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

BASE_URL = "http://digitec.ch"
LIVE_URL = "http://digitec.ch/de/SocialShopping/GetFeedData/1"


class Crawler(threading.Thread):
    HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36",
               "accept-encoding": "gzip, deflate, sdch, br",
               "x-requested-with": "XMLHttpRequest",
               "accept-language": "de-DE,de;q=0.8,en-US;q=0.6,en;q=0.4",
               "accept": "*/*",
               "referer": "https://www.digitec.ch/de/wiki/2736",
               "authority": "www.digitec.ch"}


    def __init__(self):
        super().__init__()
        self.__up = False
        signal.signal(signal.SIGINT, self.signal_handler)
        self.__session = None
        self.initialize_session()

    def signal_handler(self, *_):
        self.__up = False
        self.join()

    def initialize_session(self):
        self.__session = requests.Session()
        self.__session.get(BASE_URL, headers=self.HEADERS)

    @staticmethod
    def get_transaction_attr(transaction, name):
        val = transaction.find_all("span", {"class": name})
        return val[0].get_text() if val else ""

    def crawl(self):
        trans_time = datetime.now() - timedelta(hours=2)
        data = {"minTransactionTime": trans_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "languageId": 2,
                "_": 1337}

        try:
            res = self.__session.get(LIVE_URL, params=data,
                                      headers=self.HEADERS)
        except requests.exceptions.ConnectionError as exc:
            print("Connection error:", exc)
            print("Reinitializing session ...")
            self.initialize_session()
            return False

        soup = BeautifulSoup(res.text, "html.parser")
        transactions = soup.find_all("div")
        print("Found", len(transactions), "transactions")
        for transaction in transactions:
            timestamp = transaction.get("data-transaction-time")
            if not timestamp:
                print("No timestamp found")
                continue

            timestamp = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S")
            brand = self.get_transaction_attr(transaction, "brand").strip()
            product = self.get_transaction_attr(transaction, "product").strip()
            price = self.get_transaction_attr(transaction, "price").strip()

            full_trans = transaction.get_text()
            full_trans = re.sub(" +", " ", full_trans)
            full_trans = re.sub("\n", "", full_trans)

            location = re.search("from (.*)( just | is )", full_trans)
            location = location.group(1).strip() if location else ""
            name = re.search("([0-9][0-9]:[0-9][0-9])(.*) from", full_trans)
            name = name.group(2).strip() if name else ""

            _file = None
            if "just ordered" in full_trans:
                _file = "orders.csv"
                line = "{}|{}|{}|{}|{}|{}|\n".format(timestamp, location, name, brand, product, price)
            elif "is looking for" in full_trans:
                search_term = re.search("( is looking for )(.*)", full_trans)
                _file = "searches.csv"
                line = "{}|{}|{}|{}|\n".format(timestamp, location, name, search_term.group(2).strip())
            elif "is looking at" in full_trans:
                _file = "productsearches.csv"
                line = "{}|{}|{}|{}|{}|{}|\n".format(timestamp, location, name, brand, product, price)
            else:
                _file = "other.csv"
                line = "{}|{}|\n".format(timestamp, full_trans)

            with open(_file, "a+") as output:
                output.write(line)
                output.flush()

        return True

    def run(self):
        self.__up = True
        while self.__up:
            if not self.crawl():
                time.sleep(5)
                continue
            for _ in range(0, 60):
                if not self.__up:
                    return
                time.sleep(1)

def main():
    crawler = Crawler()
    crawler.start()

if __name__ == "__main__":
    main()
