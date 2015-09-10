import tornado.web
import fetcher
import parser
from parser import convertUrl
from tornado.gen import coroutine, maybe_future
import tornado.gen
import logging
import json
from tornado.options import options
import os


logger = logging.getLogger("View")


@coroutine
def get_data(url, handler):
    key = parser.convertUrl(url)
    cached = yield fetcher.get_data(key)
    if cached:
        return cached
    result = yield fetcher.get_page(url)
    ret = yield maybe_future(handler(result))
    ret = json.dumps(ret)
    yield fetcher.write_data(key, ret, options.CACHE_TIME)
    return ret


def merge(x, y):
    z = x.copy()
    z.update(y)
    return z


def makeUrl(type, **kwargs):

    logger.debug("make url %s, %s", type, kwargs)

    if "post" == type:
        return "http://www.new1.uestc.edu.cn/?n=UestcNews.Front.Document.ArticlePage&Id={Id}".format_map(kwargs)
    elif "category" == type:
        kwargs['page'] = kwargs.get("page", "1")
        return "http://www.new1.uestc.edu.cn/?n=UestcNews.Front.Category.Page&CatId={CatId}&page={page}".format_map(kwargs)
    elif "index" == type:
        return "http://www.uestc.edu.cn"
    else:
        logger.warn("unknown type")
        raise NotImplemented


class News(tornado.web.RequestHandler):

    """
    单条新闻内容
    """

    @coroutine
    def get(self, pid):
        self.set_header("Content-type", 'application/json')
        url = makeUrl('post', Id=pid)
        content = yield get_data(url, parser.ParsePost)
        self.write(content)


class Index(tornado.web.RequestHandler):

    """
    首页
    轮播图数据来自于 "焦点新闻"
    下方新闻来自于首页的新闻汇总
    """

    @coroutine
    def deal(self, content):
        general = parser.ParseIndexGeneral(content)

        subCategory = parser.ParseIndexSubCategory(content)
        general_link = yield [get_data(i[1], parser.ParsePost) for i in general]
        general = [merge(json.loads(general_link[i]), {"link": convertUrl(general[i][1])}) for i in range(len(general))]
        return {
            "general": general,
            "subCategory": subCategory,
        }

    @coroutine
    def get(self):
        self.set_header("Content-type", 'application/json')
        content = yield get_data(makeUrl("index"), self.deal)
        self.write(content)


class NewsCategory(tornado.web.RequestHandler):

    @coroutine
    def get(self, cid):
        self.set_header("Content-type", 'application/json')
        page = self.get_argument('page', '1')
        content = yield get_data(makeUrl('category', page=page, CatId=cid), parser.ParseCategory)
        self.write(content)


class RedirectStaticFileHandler(tornado.web.StaticFileHandler):

    def initialize(self, path, default_filename=None):
        root, self.filename = os.path.split(path)
        super(RedirectStaticFileHandler, self).initialize(root)

    @coroutine
    def get(self, include_body=True):
        yield super(RedirectStaticFileHandler, self).get(self.filename)


class CleanCache(tornado.web.RequestHandler):

    def get(self):
        source_ip = self.request.remote_ip
        logger.warn("The redis is cleared by users: %s", source_ip)
        fetcher.r.flushdb()
        self.write("401 YOU ARE ON THE WRONG PAGE")
