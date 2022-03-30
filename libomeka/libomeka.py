import json
import requests
import os
# from lib import Curation
import Curation

class Omeka:
    api = ""
    key = ""
    output_dir = ""

    types = [
        "collections", 
        "element_sets", 
        "elements", 
        "files", 
        "item_types",
        "tags",
        # "users"
    ]

    def loadEnv(self, file):
        with open(file) as f:
            env = json.load(f)

        self.api = env["api"]
        self.key = env["key"]
        self.output_dir = env["output_dir"]

    def downloadAllResources(self):
        for type in self.types:
            self.downloadResources(type)
    
    def downloadResources(self, type="items"):
        api_url = self.api
        key = self.key

        loop_flg = True
        page = 1

        dir = "{}/api/{}".format(self.output_dir, type)
        os.makedirs(dir, exist_ok=True)

        while loop_flg:
            url = "{}/{}?page={}".format(api_url, type, page)

            if key != "":
                url += "&key="+key

            print(url)

            page += 1

            headers = {"content-type": "application/json"}
            r = requests.get(url, headers=headers)
            data = r.json()

            if len(data) > 0:
                for i in range(len(data)):
                    obj = data[i]

                    id = obj["id"]

                    uri = "{}/{}.json".format(api_url, id)

                    obj["@id"] = uri

                    with open("{}/{}.json".format(dir, id), 'w') as outfile:
                        json.dump(obj, outfile, ensure_ascii=False,
                                indent=4, sort_keys=True, separators=(',', ': '))

            else:
                loop_flg = False

    def createCuration(self):
        Curation.create(self.output_dir)
