import lxml.html
import requests
from unidecode import unidecode
import time
import random
from syncano import client
import datetime
import json
from textblob.classifiers import NaiveBayesClassifier as NBC
from textblob.classifiers import DecisionTreeClassifier as DTC

from textblob import TextBlob
import os
from postmark import PMMail
import pickle

#a web scraper integrated with syncano
class Scraper:
    def __init__(self,
                 instance_name="white-sun-672290",
                 api_key="92f4c3ae210cee23a24c03f892574fa9957cdf30",
                 project_id="6128",
                 collection_id="18661",
                 base_urls=[
                     "http://newyork.backpage.com/FemaleEscorts/",
                     "http://newyork.backpage.com/BodyRubs/",
                     "http://newyork.backpage.com/Strippers/",
                     "http://newyork.backpage.com/Domination/",
                     "http://newyork.backpage.com/TranssexualEscorts/",
                     "http://newyork.backpage.com/MaleEscorts/",
                    "http://newyork.backpage.com/Datelines/",
                     "http://newyork.backpage.com/AdultJobs/"
                 ],
                 child_keywords=[],
                 trafficking_keywords=[]
    ):
        self.base_urls = base_urls
        self.instance_name = instance_name
        self.api_key = api_key
        self.project_id = project_id
        self.collection_id = collection_id
        self.child_keywords = child_keywords
        self.trafficking_keywords = trafficking_keywords

    def letter_to_number(self,text):
        text= text.upper()
        text = text.replace("ONE","1")
        text = text.replace("TWO","2")
        text = text.replace("THREE","3")
        text = text.replace("FOUR","4")
        text = text.replace("FIVE","5")
        text = text.replace("SIX","6")
        text = text.replace("SEVEN","7")
        text = text.replace("EIGHT","8")
        text = text.replace("NINE","9")
        text = text.replace("ZERO","0")
        return text

    def phone_number_parse(self,values):
        text = self.letter_to_number(values["text_body"])
        phone = []
        counter = 0
        found = False
        for ind,letter in enumerate(text):
            if letter.isdigit():
                phone.append(letter)
                found = True
            else:
                if found:
                    counter += 1
                if counter > 13 and found:
                    phone = []
                    counter = 0
                    found = False

            if len(phone) == 10 and phone[0] != '1':
                values["phone_number"] = ''.join(phone)
                return values
            if len(phone) == 11 and phone[0] == '1':
                values["phone_number"] = ''.join(phone)
                return values

        values["phone_number"] = ''
        return values
    
    def scrape(self,links=[],auto_learn=False,long_running=False,translator=False):
        responses = []
        values = {}
        data = []

        if links == []:
            for base_url in self.base_urls:
                r = requests.get(base_url)
                text = unidecode(r.text)
                html = lxml.html.fromstring(text)

                links = html.xpath("//div[@class='cat']/a/@href")
                for link in links:
                    if len(self.base_urls) > 1 or len(self.base_urls[0]) > 3:
                        time.sleep(random.randint(1,2))
                        if long_running:
                            time.sleep(random.randint(5,27))
                    try:
                        responses.append(requests.get(link))
                        print link
                    except requests.exceptions.ConnectionError:
                        print "hitting connection error"
                        continue
        else:
            for link in links:
                if len(self.base_urls) > 1 or len(self.base_urls[0]) > 3:
                    time.sleep(random.randint(1,2))
                    if long_running:
                        time.sleep(random.randint(5,17))
                try:
                    responses.append(requests.get(link))
                    print link
                except requests.exceptions.ConnectionError:
                    print "hitting connection error"
                    continue

        for r in responses:
            text = r.text
            html = lxml.html.fromstring(text)
            values["title"] = html.xpath("//div[@id='postingTitle']/a/h1")[0].text_content()
            values["link"] = unidecode(r.url)
            values["new_keywords"] = []
            try:
                values["images"] = html.xpath("//img/@src")
            except IndexError:
                values["images"] = "weird index error"
            pre_decode_text = html.xpath("//div[@class='postingBody']")[0].text_content().replace("\n","").replace("\r","")  
            values["text_body"] = pre_decode_text 
            try:
                values["posted_at"] = html.xpath("//div[class='adInfo']")[0].text_content().replace("\n"," ").replace("\r","")
            except IndexError:
                values["posted_at"] = "not given"
            values["scraped_at"] = str(datetime.datetime.now())
            body_blob = TextBlob(values["text_body"])
            title_blob = TextBlob(values["title"])
            values["language"] = body_blob.detect_language() #requires the internet - makes use of google translate api
            values["polarity"] = body_blob.polarity
            values["subjectivity"] = body_blob.sentiment[1]
            translated = translator or values["language"] == "es"
            if translated:
                values["translated_body"] = body_blob.translate(from_lang="es")
                values["translated_title"] = title_blob.translate(from_lang="es")
            else:
                values["translated_body"] = "none"
                values["translated_title"] = "none"
            text_body = values["text_body"]
            title = values["title"]

            if translated:
                text_body = values["translated_body"]
                title = values["translated_title"]

            if auto_learn:
                train = pickle.load(open("train.p","rb"))
                cls = []
                cls.append(NBC(train))
                cls.append(DTC(train))
                #increase this number
                trk_count = 0
                for cl in cls:
                    if cl.classify(text_body) == "trafficking":
                        trk_count += 1

                if float(trk_count)/len(cls) > 0.5:
                    train = pickle.load(open("train.p","rb"))
                    train.append((values["text_body"],"trafficking") )
                    pickle.dump(train,open("train.p","wb"))
                    values["trafficking"] = "found"
                else:
                    values["trafficking"] = "not_found"
                #To do set up postmark here.
                #Documentation: https://devcenter.heroku.com/articles/postmark
                #even more docs: https://postmarkapp.com/servers/645009/get_started
                
            else:
                values["trafficking"] = "not_found"
                           
            values["child_urls"] = []
            for keyword in self.child_keywords:
                if keyword in text_body:
                    values["child_urls"].append(values["link"])
                elif keyword in title:
                    values["child_urls"].append(values["link"])

            values["trafficking_urls"] = []
            for keyword in self.trafficking_keywords:
                if keyword in text_body:
                    values["trafficking_urls"].append(values["link"])
                elif keyword in title:
                    values["trafficking_urls"].append(values["link"])

            values["new_keywords"].append(self.pull_keywords(text_body))
            values["new_keywords"].append(self.pull_keywords(title))
            values = self.phone_number_parse(values)
            numbers = pickle.load(open("numbers.p","rb"))
            values["network"] = []
            for network in numbers.keys():
                if values["phone_number"] in numbers[network]:
                    values["network"].append(network)
            data.append(values)
        self.save_ads(data)
        return data

    def pull_keywords(self,text):
        text = text.lower()
        ignore_words = ["and","or","to","an","to","like","all","am","your","I","who"," ",'']
        new_text = []
        for word in text.split(" "):
            if not word in ignore_words:
                new_text.append(word)
        return new_text
    
    def save_ads(self,data):
        SyncanoApi = client.SyncanoApi
        with SyncanoApi(self.instance_name,self.api_key) as syncano:
            for datum in data:
                syncano.data_new(
                    self.project_id,
                    collection_id=self.collection_id,
                    title=datum["title"],
                    phone_number=datum["phone_number"],
                    text_body=datum["text_body"],
                    text=json.dumps(datum["images"]),
                    link=datum["link"],
                    posted_at = datum["posted_at"],
                    scraped_at=datum["scraped_at"],
                    flagged_for_child_trafficking=json.dumps(datum["child_urls"]),
                    flagged_for_trafficking=json.dumps(datum["trafficking_urls"]),
                    language=datum["language"],
                    polarity=datum["polarity"],
                    translated_body=datum["translated_body"],
                    translated_title=datum["translated_title"],
                    subjectivity=datum["subjectivity"],
                    network=json.dumps(datum["network"]),
		    blarg="anything",
		    hello="butts"
                )
    
if __name__ == '__main__':
    scraper = Scraper(base_urls=["http://newyork.backpage.com/FemaleEscorts/"])
    data = scraper.scrape()
    
    
