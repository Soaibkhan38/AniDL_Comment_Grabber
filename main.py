import json
import requests
import feedparser
import dbm
import re
from dataclasses import dataclass
from datetime import timedelta, datetime
from dateutil import parser
from time import sleep

DEFAULT_MESSAGE_PREFIX = "New post:"

@dataclass
class Config:
    """Configuration for tg-feed-bot.
    """
    db_path: str
    feed_url: str
    telegram_token: str
    chat_id: int
    message_prefix: str

    @staticmethod
    def from_file(filename):
        d = json.load(open(filename))
        return Config(
            db_path=d['db_path'],
            feed_url=d['feed_url'],
            telegram_token=d['telegram_token'],
            chat_id=d['chat_id'],
            message_prefix=d.get('message_prefix') or DEFAULT_MESSAGE_PREFIX)

class FeedBot:
    """Telegram Bot to notify a telegram channel for every new entry in the RSS/Atom feed.
    """
    def __init__(self, config: Config):
        self.config = config
        self.db = dbm.open(config.db_path, 'c')

    def run(self):
        d = feedparser.parse(self.config.feed_url)
        for entry in d.entries[::-1]:
            self.notify(entry)

    def notify(self, entry):
        url = self.find_link(entry)
        if url in self.db:
            print(f"Entry for {url} is already posted. ignoring...")
            return

        print(f"Posting notification for {url}...")
        message = self.prepare_message(url, entry)

        self.send_telegram_message(
            token=self.config.telegram_token,
            chat_id=self.config.chat_id,
            message=message)
        self.db[url] = "true"

    def prepare_message(self, url, entry):
        prefix = self.config.message_prefix
        title = entry.title
        author = entry.author
        summary = entry.summary.replace("<p>","").replace("</p>", "")
        summary = summary.replace("<","").replace(">","")
        date = parser.parse(entry.published).replace(tzinfo=None)
        #print(parsed_date)
        date = (date + timedelta(hours=4)).replace(tzinfo=None)
        # Replace any @foo in the author name as that would conflict
        # with usernames in telegram
        # Added to deal with the feeds of discord
        author = re.sub("@\w+", "", author).strip()

        return "<i>"+str(prefix)+"</i> <a href=\""+str(url)+"\">"+str(title)+"</a>\n<b>"+str(author)+"</b> <i>wrote at "+str(date)+":</i>\n"+str(summary)

    def send_telegram_message(self, token, chat_id, message):
        url = f'https://api.telegram.org/bot{token}/sendMessage'
        data = {'chat_id': chat_id, 'text': message, 'parse_mode': 'html'}
        res = requests.post(url, data).json()
        if not res.get("ok"):
            raise Exception("Failed to send message to telegram: %s", res)

    def find_link(self, entry):
        return first(link['href'] for link in entry.links if link.type == "text/html")

def first(seq):
    try:
        return next(iter(seq))
    except StopIteration:
        return None

def main():
    config = Config.from_file("config.json")
    bot = FeedBot(config)
    bot.run()

if __name__ == "__main__":
    while True:
        main()
        sleep(5*60)
