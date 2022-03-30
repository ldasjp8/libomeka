import sys
import urllib
import json
import argparse
import requests
import os
import shutil
import yaml
import glob
import hashlib

import re
# as per recommendation from @freylis, compile once only
CLEANR = re.compile('<.*?>') 

def cleanhtml(raw_html):
  cleantext = re.sub(CLEANR, '', raw_html)
  return cleantext

def getGitHubHostingPrefix(env):
    github_id = env["github"]

    spl = github_id.split("/")

    username = spl[0]
    repository = spl[1]

    prefix = "https://{}.github.io/{}".format(username, repository)

    return prefix

def extractInfoFromItem(file):
    with open(file) as f:
        item = json.load(f)

    metadata = {}
    element_texts = item["element_texts"]

    for e in element_texts:
        metadata[e["element"]["name"]] = e["text"]

    if item["item_type"] and item["item_type"]["name"] == "Annotation":
        
        
        region = metadata["Annotated Region"]

        if "Text" not in metadata:
            return {
                "status": "error",
                "message": '''"Text" not in metadata'''
            }

        value = metadata["Text"]
        canvas_uuid = metadata["On Canvas"]

        tags = []
        for tag in item["tags"]:
            tags.append(tag["name"])

        metadata2 = [
            {
                "label": "public",
                "value": item["public"]
            },
            {
                "label": "featured",
                "value": item["featured"]
            },
            {
                "label": "modified",
                "value": item["modified"].split("T")[0]
            },
            {
                "label": "added",
                "value": item["added"].split("T")[0]
            }
        ]

        metadata2.append({
            "label": "tags",
            "value": tags
        })

        return {
            "type": "Annotation",
            "canvas_uuid": canvas_uuid,
            "xywh": region,
            "label": cleanhtml(value).strip(),
            "metadata": metadata2
        }

    else:
        canvas_uuid = metadata["UUID"]
        canvas_id = metadata["Original @id"]

        manifest = metadata["Source"]

        result = {
            "type": "Manifest",
            "canvas_uuid": canvas_uuid,
            "canvas_id": canvas_id,
            "manifest": manifest,
            "collection": item["collection"]["id"] if item["collection"] else "None"
        }

        return result

def getManifestData(manifest):
    hash = hashlib.md5(manifest.encode('utf-8')).hexdigest()

    odir = "tmp/manifest"
    os.makedirs(odir, exist_ok=True)

    path = "{}/{}.json".format(odir, hash)

    if not os.path.exists(path):

        try:
            df = requests.get(manifest).json()
        except Exception as e:
            return {
                "status": "error",
                "message": e
            }

        with open(path, 'w') as outfile:
            json.dump(df, outfile, ensure_ascii=False,
                        indent=4, sort_keys=True, separators=(',', ': '))

    with open(path) as f:
        m = json.load(f)

    return m #

def create(output_dir):
    prefix = "http://localhost"

    dir = "{}/api/items".format(output_dir)

    files = glob.glob(dir+"/*.json")

    members = {}
    collections = {}

    for file in files:

        result = extractInfoFromItem(file)

        if "message" in result:
            print('エラー1: OmekaからダウンロードしたJSONファイルに不具合があります。{},{}'.format(result["message"], file), file=sys.stderr)
            continue

        result_type = result["type"]

        if result_type == "Annotation":
            canvas_uuid = result["canvas_uuid"]
            if canvas_uuid not in members:
                members[canvas_uuid] = []
            
            members[canvas_uuid].append(result)

        else:
            collection_id = result["collection"]

            if collection_id not in collections:
                collections[collection_id] = {
                    "manifest": result["manifest"],
                    "canvases": {}
                }

            collections[collection_id]["canvases"][result["canvas_id"]] = result["canvas_uuid"]

    selections = []

    for collection_id in collections:
        collection = collections[collection_id]
        manifest = collection["manifest"] # collections[collection]

        manifestData = getManifestData(manifest)

        if "message" in manifestData:
            print('エラー3: IIIFマニフェストファイルに不具合があります。{},{}'.format(manifestData["message"], manifest), file=sys.stderr)
            continue

        canvases = manifestData["sequences"][0]["canvases"]

        canvasesFromOmeka = collection["canvases"]

        members_new = []

        for canvas in canvases:
            canvas_id = canvas["@id"]

            if canvas_id in canvasesFromOmeka:
                canvas_uuid = canvasesFromOmeka[canvas_id]

                if canvas_uuid not in members: # ちょっとなぞ
                    print('エラー2: membersに存在しないcanvas_uuidを参照しています。{}'.format(canvas_uuid), file=sys.stderr)
                    continue

                members_ = members[canvas_uuid]

                for member in members_:
                    member_ = {
                        "@id" : "{}#xywh={}".format(canvas_id, member["xywh"]),
                        "label" : member["label"],
                        "@type": "sc:Canvas",
                        "metadata": member["metadata"]
                    }

                    members_new.append(member_)

        if len(members_new) > 0:
            selection = {
                "@id": manifest+"/range",
                "@type": "sc:Range",
                "label":  manifestData["label"],
                "members" : members_new,
                "within" : {
                    "@id" : manifest,
                    "@type": "sc:Manifest",
                    "label" : manifestData["label"]
                }
            }
            selections.append(selection)

    curation = {
        "@context": [
            "http://iiif.io/api/presentation/2/context.json",
            "http://codh.rois.ac.jp/iiif/curation/1/context.json"
        ],
        "@type": "cr:Curation",
        "@id" : prefix + "/iiif/curation/top.json",
        "label" : "IIIF Toolkit",
        "selections" : selections
    }

    opath = "{}/iiif/curation/top.json".format(output_dir)
    dirname = os.path.dirname(opath)
    os.makedirs(dirname, exist_ok=True)

    with open(opath, 'w') as outfile:
        json.dump(curation, outfile, ensure_ascii=False,
                    indent=4, sort_keys=True, separators=(',', ': '))


