# -*- coding: utf-8 -*-

from cgi import FieldStorage
from Cookie import SimpleCookie, CookieError
from datetime import date, datetime, time
from functools import update_wrapper
import re
try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO
import traceback
from urlparse import parse_qsl

import dateutil
import dateutil.tz

STATUSES = {
    100: 'Continue',
    101: 'Switching Protocols',
    102: 'Processing',
    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',
    207: 'Multi-Status',
    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    307: 'Temporary Redirect',
    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    406: 'Not Acceptable',
    407: 'Proxy Authentication Required',
    408: 'Request Timeout',
    409: 'Conflict',
    410: 'Gone',
    411: 'Length Required',
    412: 'Precondition Failed',
    413: 'Request Entity Too Large',
    414: 'Request-URI Too Long',
    415: 'Unsupported Media Type',
    416: 'Requested Range Not Satisfiable',
    417: 'Expectation Failed',
    422: 'Unprocessable Entity',
    423: 'Locked',
    424: 'Failed Dependency',
    425: 'Unordered Collection',
    426: 'Upgrade Required',
    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
    505: 'HTTP Version Not Supported',
    506: 'Variant Also Negotiates',
    507: 'Insufficient Storage',
    509: 'Bandwidth Limit Exceeded',
    510: 'Not Extended',
}

class Routing(object):
    def __init__(self, route):
        path = [route]
        rpath = [] # For exceptions, so we know which target was wrong
        # TODO: Implement those exceptions...

        def _make_route(r):
            output = []
            for regex, target in r:
                rpath.append(regex)
                regex = re.compile(regex)
                if type(target) in (list, tuple):
                    if target in path:
                        print rpath
                        raise Exception('Loop found in route!')
                    path.append(target)
                    target = _make_route(target)
                    path.pop()
                elif isinstance(target, basestring):
                    # TODO: Implement importing
                    print rpath
                    raise NotImplementedError('String targets not yet supported')
                elif not callable(target):
                    print rpath
                    raise Exception('Unsupported target type!')
                rpath.pop()
                output.append((regex, target))
            return tuple(output)

        self.routing = _make_route(route)

    def route_request(self, request):
        a = self.routing
        start = 0
        args = {}
        while True:
            found = None
            for regex, target in a:
                g = regex.match(request.mpath, start)
                if g:
                    args.update(g.groupdict())
                    start = g.end()
                    if callable(target):
                        return (args, target)
                    else:
                        found = target
                        break
            if found:
                a = found
            else:
                return None

class Application(object):
    def __init__(self, routing, default_type='text/html', default_encoding='utf-8', mountpoint='/'):
        self.route = routing
        self.default_type = default_type
        self.default_encoding = default_encoding
        self.mountpoint = mountpoint

    def __call__(self, environ, start_response):
        request = Request(environ, self)
        target = self.route.route_request(request)
        if target:
            args, target = target
            try:
                response = target(request, **args)
            except:
                tb = traceback.format_exc()
                print tb
                response = Response(tb, 500, 'text/plain')
            
            if not isinstance(response, Response):
                response = Response(response)
        else:
            response = Response('Not found!', 404, 'text/plain')

        response.default_type = self.default_type
        response.default_encoding = self.default_encoding

        return response.do_respond_wsgi(start_response)

class Request(object):
    def __init__(self, environ, app=None):
        self.mpath = self.path = environ['PATH_INFO']
        if app and self.path.startswith(app.mountpoint):
            self.mpath = self.path[len(app.mountpoint):]

        self.method = environ['REQUEST_METHOD'].upper()

        try:
            self.content_length = int(environ.get('HTTP_CONTENT_LENGTH', 0))
        except:
            self.content_length = 0

        self.content_type = environ.get('CONTENT_TYPE', '').lower()

        self.META = environ
        self.app = app

        self._get = None
        self._cookies = None
        self._post = None
        self._files = None

        self._raw_fp = None

    def _get_mdict(self, qs):
        return MultiDict(parse_qsl(qs, True))

    def _get_get(self):
        if self._get is None:
            self._get = self._get_mdict(self.META.get('QUERY_STRING', ''))
        return self._get
    
    def _get_cookies(self):
        if self._cookies is None:
            self._cookies = {}
            cookie = self.META.get('HTTP_COOKIE', '')
            if cookie:
                try:
                    cookie = SimpleCookie(cookie)
                except CookieError:
                    pass
                else:
                    for key in cookie.iterkeys():
                        self._cookies[key] = cookie[key].value
        return self._cookies

    def _get_post(self):
        if self._post is None:
            self._parse_input()
        return self._post

    def _parse_input(self):
        self._post = MultiDict()
        self._files = MultiDict()

        fp = None

        if self.method == 'POST':
            ctype = self.content_type.split(';')[0]

            if self.content_length:
                fp = self.META.get('wsgi.input', None)

            if fp and ctype in ('application/x-www-form-urlencoded', 'multipart/form-data'):
                environ = {
                    'REQUEST_METHOD': 'POST',
                    'CONTENT_TYPE': self.content_type,
                    'CONTENT_LENGTH': str(self.content_length),
                }
                fields = FieldStorage(fp=fp, environ=environ, keep_blank_values=True)
                print fields

                for key in fields.keys():
                    print key
                    if not key:
                        continue

                    values = fields[key]
                    print values
                    if not isinstance(values, list):
                        values = [values]

                    for value in values:
                        if value.file:
                            print 'Files not yet supported. Filename: "%s" Field name: "%s" Content-type: "%s"' % \
                                    (value.filename, key, value.type)
                        else:
                            self._post.add(key, value.value)
                fp = None

        self._raw_fp = fp or StringIO()

    def _get_fp(self):
        if self._raw_fp is None:
            self._parse_input()
        return self._raw_fp

    GET = property(_get_get)
    COOKIES = property(_get_cookies)
    POST = property(_get_post)
    fp = property(_get_fp)

class Response(object):
    def __init__(self, content=None, status=200, content_type='text/html', encoding='utf-8', headers=None): #, default_type='text/html', default_encoding='utf-8'):
        status = int(status)
        self.content = content
        self.status = status if status in STATUSES else 200
        self.content_type = content_type
        self.encoding = encoding
        self.headers = headers or {}
        #self.default_type = default_type
        #self.default_encoding = default_encoding

        self.cookies = SimpleCookie()

    def set_cookie(self, key, value='', max_age=None, expires=None, path='/', domain=None, secure=False):
        if expires:
            t = type(expires)
            if t == date:
                expires = datetime(expires.year, expires.month, expires.day)
            elif t == time:
                expires = datetime.now().replace(hour=expires.hour, minute=expires.minute, second=expires.second)
            elif t in (int, long):
                expires = datetime.fromtimestamp(expires)
            else:
                Exception('Cookie expire time has incorrect type')

            if not (hasattr(expires, 'tzinfo') and expires.tzinfo):
                expires = expires.replace(tzinfo=dateutil.tz.tzlocal())
            expires = expires.strftime('%a, %d %b %Y %H:%M:%S %z')

        self.cookies[key] = value
        cookie = self.cookies[key]
        if max_age is not None:
            cookie['max-age'] = max_age
        if expires is not None:
            cookie['expires'] = expires
        if path is not None:
            cookie['path'] = path
        if domain is not None:
            cookie['domain'] = domain
        if secure:
            cookie['secure'] = True

    def delete_cookie(self, key, path='/', domain=None):
        self.set_cookie(key, max_age=0, path=path, domain=domain, expires=datetime(1970, 1, 1))

    def prepare(self):
        #self.content_type = self.content_type or self.default_type
        #self.encoding = self.encoding or self.default_encoding

        if isinstance(self.content, unicode):
            self.content = self.content.encode(self.encoding)
        elif not isinstance(self.content, str):
            self.content = str(self.content)
    
    def do_respond_wsgi(self, start_response):
        self.prepare()
        status = '%s %s' % (self.status, STATUSES[self.status])
        headers = self.headers.items()
        if self.content_type:
            if self.encoding:
                headers.append(
                    ('Content-type', '%s; charset=%s' % (self.content_type, self.encoding))
                )
            else:
                headers.append(
                    ('Content-type', '%s' % self.content_type)
                )
        if self.cookies:
            for c in self.cookies.values():
                headers.append(('Set-Cookie', str(c.output(header=''))))
        start_response(status, headers)
        return self.content

class ResponseRedirect(Response):
    def __init__(self, location):
        self.headers = {}
        self.location = location

        self.cookies = SimpleCookie()

    def prepare(self):
        self.headers['Location'] = self.location
        self.status = 302
        self.content = None
        self.content_type = None

class ResponseProto(object):
    def __init__(self, content_type=None, encoding=None):
        self.cookies = {}
        self.content_type = content_type
        self.encoding = encoding
        self.status = 200
        self.headers = {}
        self._response = None

    def set_cookie(self, key, value='', max_age=None, expires=None, path='/', domain=None, secure=False):
        self.cookies[key] = (key, value, max_age, expires, path, domain, secure)
        
    def delete_cookie(self, key, path='/', domain=None):
        self.set_cookie(key, max_age=0, path=path, domain=domain, expires=datetime(1970, 01, 01))

    def redirect(self, location):
        if self._response: return self._response
        r = ResponseRedirect(location)
        self._apply(r)
        self._response = r
        return r

    def make_response(self, content):
        if self._response: return self._response
        r = Response(
            content,
            status=self.status,
            content_type=self.content_type,
            encoding=self.encoding,
            headers=self.headers,
        )
        self._apply(r)
        self._response = r
        return r

    def _apply(self, response):
        for v in self.cookies.itervalues():
            response.set_cookie(*v)

class Controller(object):
    def __init__(self, w, content_type=None, encoding=None):
        if callable(w):
            self._f = w
        else:
            self._f = lambda *a, **k: w

        self.content_type = content_type
        self.encoding = encoding

    def __call__(self, request, *args, **kwargs):
        proto = ResponseProto(
            self.content_type or request.app.default_type,
            self.encoding or request.app.default_encoding,
        )
        res = self._f(request, proto, *args, **kwargs)
        if isinstance(res, Response):
            return res
        return proto.make_response(res)

def expose(_f=None, content_type=None, encoding=None):
    def decorator(f):
        return update_wrapper(Controller(f, content_type, encoding), f)

    if _f is None or not callable(_f):
        return decorator
    else:
        return decorator(_f)

class MultiDict(dict):
    '''
    Small ripoff of django's MultiValueDict...
    I don't see any need to do more. At least not now.
    '''

    def get1(self, key, default=None):
        v = self.get(key, default)
        if isinstance(v, list):
            v = v[-1] if v else default
        return v

    def add(self, key, value):
        self.setdefault(key, []).append(value)
