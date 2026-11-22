import json
import os
import time

import requests

from .config import GRAPH


class MetaError(Exception):
    pass


def _call(method, path, **params):
    params["access_token"] = os.environ["PAGE_ACCESS_TOKEN"]
    kw = {"params": params} if method == "GET" else {"data": params}
    r = requests.request(method, f"{GRAPH}/{path}", timeout=20, **kw)
    try:
        j = r.json()
    except ValueError:
        j = {}
    if r.status_code >= 400 or "error" in j:
        err = j.get("error", {})
        raise MetaError(f"{r.status_code} {err.get('message', r.text[:200])}")
    return j


def get(path, **p):
    return _call("GET", path, **p)


def post(path, **p):
    return _call("POST", path, **p)


def page_id():
    return os.environ["PAGE_ID"]


def ig_id():
    return os.environ["IG_USER_ID"]


# ---------- Publishing ----------
def publish_instagram(image_url, caption):
    c = post(f"{ig_id()}/media", image_url=image_url, caption=caption)["id"]
    for _ in range(20):
        st = get(c, fields="status_code").get("status_code")
        if st == "FINISHED":
            break
        if st == "ERROR":
            raise MetaError("Instagram image process fail hui")
        time.sleep(3)
    media_id = post(f"{ig_id()}/media_publish", creation_id=c)["id"]
    try:
        return get(media_id, fields="permalink").get("permalink", media_id)
    except MetaError:
        return media_id


def publish_facebook(image_url, caption):
    r = post(f"{page_id()}/photos", url=image_url, caption=caption, published="true")
    pid = r.get("post_id") or r.get("id")
    return f"https://www.facebook.com/{pid}"


# ---------- Comments ----------
def ig_username():
    return get(ig_id(), fields="username").get("username", "")


def ig_recent_media(limit=8):
    return get(f"{ig_id()}/media", fields="id,timestamp", limit=limit).get("data", [])


def ig_comments(media_id):
    return get(f"{media_id}/comments",
               fields="id,text,username,timestamp,replies{username}",
               limit=50).get("data", [])


def ig_reply_comment(comment_id, text):
    return post(f"{comment_id}/replies", message=text)


def fb_recent_posts(limit=8):
    return get(f"{page_id()}/posts", fields="id,created_time", limit=limit).get("data", [])


def fb_comments(post_id):
    return get(f"{post_id}/comments",
               fields="id,message,from{id,name},created_time,comments.limit(10){from{id}}",
               limit=50).get("data", [])


def fb_reply_comment(comment_id, text):
    return post(f"{comment_id}/comments", message=text)


# ---------- DMs ----------
def conversations(platform):
    """platform: 'instagram' ya 'messenger'. Har conversation ka aakhri message."""
    return get(f"{page_id()}/conversations", platform=platform,
               fields="id,messages.limit(1){id,message,from,created_time}",
               limit=20).get("data", [])


def send_dm(platform, recipient_id, text):
    p = dict(recipient=json.dumps({"id": recipient_id}),
             message=json.dumps({"text": text}))
    if platform == "messenger":
        p["messaging_type"] = "RESPONSE"
    return post(f"{page_id()}/messages", **p)


# ---------- Carousel (kayi images) ----------
def publish_instagram_carousel(image_urls, caption):
    kids = [post(f"{ig_id()}/media", image_url=u, is_carousel_item="true")["id"] for u in image_urls]
    c = post(f"{ig_id()}/media", media_type="CAROUSEL", children=",".join(kids), caption=caption)["id"]
    for _ in range(20):
        st = get(c, fields="status_code").get("status_code")
        if st == "FINISHED":
            break
        if st == "ERROR":
            raise MetaError("Instagram carousel process fail hui")
        time.sleep(3)
    media_id = post(f"{ig_id()}/media_publish", creation_id=c)["id"]
    try:
        return get(media_id, fields="permalink").get("permalink", media_id)
    except MetaError:
        return media_id


def publish_facebook_multi(image_urls, caption):
    ids = [post(f"{page_id()}/photos", url=u, published="false")["id"] for u in image_urls]
    params = {"message": caption}
    for i, pid in enumerate(ids):
        params[f"attached_media[{i}]"] = json.dumps({"media_fbid": pid})
    r = post(f"{page_id()}/feed", **params)
    return f"https://www.facebook.com/{r.get('id')}"
