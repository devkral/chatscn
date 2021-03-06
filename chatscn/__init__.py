#! /usr/bin/env python3


import threading
import abc
import ssl
import json
import logging
import socket
import functools
import os
import pathlib
import socketserver
import time

from http import server, client
from simplescn.tools import default_sslcont, dhash, logcheck_con, logcheck, scnparse_url
#, scnparse_url
def license():
    print("This software is licensed under the MIT-License")
thisdir = os.path.dirname(__file__)

messagebuffer = {}
allowed_types = {"image", "file", "text"}

simplelock = threading.RLock()
def getticket(path, nonewticket=False):
    with simplelock:
        os.makedirs(path, 0o700, exist_ok=True)
        try:
            with open(os.path.join(path, "number"), "r+") as rowob:
                number = int(rowob.read()) + 1
                if not nonewticket:
                    rowob.seek(0, 0)
                    rowob.write(str(number))
                return number
        except:
            if not nonewticket:
                with open(os.path.join(path, "number"), "w") as rowob:
                    rowob.write("0")
            return 0

def writeBuffer(number,  certhash, newentry):
    with simplelock:
        if certhash not in messagebuffer:
            messagebuffer[certhash] = {}
        messagebuffer[number] = newentry

def writeStuff(path, certhash, dicob, isowner, writedisk=True, ticketnumber=None):
    if ticketnumber:
        luckynumber = ticketnumber
    else:
        luckynumber = getticket(os.path.join(path, certhash))
    dicob["owner"] = isowner
    dicob["time"] = int(time.time())
    dicob["number"] = luckynumber
    dicob["certhash"] = certhash
    if writedisk:
        with open(os.path.join(path, certhash, "{}.json".format(luckynumber)), "w") as waffle:
            json.dump(dicob, waffle)
    else:
        writeBuffer(luckynumber, certhash, dicob.copy())
    return dicob

def senslevel_to_text(level):
    if level == 0:
        return "normal"
    elif level == 1:
        return "private"
    elif level == 2:
        return "sensitive"
    return ""

class SCNSender(object):
    requester = None
    basedir =  None
    cur_address= None
    cur_server = None
    def __init__(self, requester, basedir):
        self.requester = requester
        self.basedir = basedir

    def do_requestdo(self, path: str, body: dict, certhash=None, name=None): #, headers: dict, **kwargs
        if not self.cur_address:
            if not certhash:
                logging.error("neither address nor certhash available")
                return None
            respw = self.requester.wrap_via_server(certhash, "chatscn", server=self.cur_server, name=name)
        else:
            body = {"name": "chatscn", "address": self.cur_address}
            if certhash:
                body["forcehash"] = certhash
            respw = self.requester.do_request("/client/wrap", body, {})
        if not logcheck_con(respw, logging.ERROR):
            return None

        con = client.HTTPConnection(*scnparse_url(respw[2].get("address", self.cur_address)))
        con.sock = respw[0].sock
        respw[0].sock = None
        ob = bytes(json.dumps(body), "utf-8")
        con.putrequest("POST", path)
        con.putheader("Content-Length", str(len(ob)))
        con.putheader("Content-Type", "application/json")
        con.endheaders()
        con.send(ob)
        respl = con.getresponse()

        if respl.status != 200:
            logging.error(str(respl.read(), "utf-8", "ignore"))
        return respl

    def send_text(self, certhash, sensitivel, text, name=None):
        body = {"text": text, "type": "text", "sensitivity": sensitivel}
        sensname = senslevel_to_text(sensitivel)
        resp = self.do_requestdo("/chat_{}/text".format(sensname), body, certhash=certhash, name=name)
        if resp and resp.status == 200:
            return writeStuff(self.basedir, certhash, body, True, writedisk=sensitivel==0)
        return None

    def send_image(self, certhash, sensitivel, filepath, caption="", name=None):
        body = {"type": "image", "caption": caption, "sensitivity": sensitivel}
        # TODO: convert/compress images, changeable size
        if os.stat(filepath).st_size > 8*1024*1024:
            logging.warning("image very big")
        with open(filepath, "r", errors='backslashreplace') as imgreob:
            body["image"] = imgreob.read()
        sensname = senslevel_to_text(sensitivel)
        resp = self.do_requestdo("/chat_{}/image".format(sensname), body, certhash=certhash, name=name)
        if resp and resp.status == 200:
            body["filepath"] = filepath
            return writeStuff(self.basedir, certhash, body, True, writedisk=sensitivel==0)
        return None

    def send_file(self, certhash, sensitivel, filepath, filename=None, name=None):
        body = {"type": "file", "sensitivity": sensitivel}
        if filename:
            body["name"] = filename
        else:
            body["name"] = os.path.basename(filepath)
        body["fileid"]  = getticket(os.path.join(self.basepath, certhash))
        sensname = senslevel_to_text(sensitivel)
        resp = self.do_requestdo("/chat_{}/file".format(sensname), body, certhash=certhash)
        if resp and resp.status == 200:
            body["filepath"] = filepath
            return writeStuff(self.basedir, certhash, body, True, ticketnumber=body["fileid"], writedisk=sensitivel==0, name=name)
        return None

async def _loadfromdir(fpath, func, data):
    try:
        with open(fpath, "r") as ro:
            job = json.load(ro)
    except Exception as exc:
        logging.info("broken file", exc)
        os.remove(fpath)
        return None
    return func(fpath, job)

def loadfromdir(basedir, func, data=None):
    ret = []
    for fpath  in sorted(pathlib.Path(basedir).iterdir()):
        #fpath = os.path.join(basedir, filename)
        if fpath.name.isdecimal():
            ret.append(_loadfromdir(fpath, func, data))
    return ret

def loadfromsocket(sock, size):
    countread = 0
    data = b""
    while countread <= size-1024:
        _data = sock.recv(1024)
        data += _data
        countread += len(_data)
    data += sock.recv(size-countread)
    return data

# TODO: max request size
class ChatHandler(server.BaseHTTPRequestHandler, metaclass=abc.ABCMeta):
    forcehash = None
    certtupel = (None, None, None)
    default_request_version = "HTTP/1.1"

    @abc.abstractmethod
    def issensitive(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def notify(self, indict):
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def basedir(self):
        raise NotImplementedError()

    def wrap(self):
        cont = default_sslcont()
        self.connection = cont.wrap_socket(self.connection, server_side=False)
        self.connection.do_handshake()
        cert = ssl.DER_cert_to_PEM_cert(self.connection.getpeercert(True)).strip().rstrip()
        if dhash(cert) != self.forcehash or self.forcehash is None:
            self.send_error(400, "invalid client or forcehash==None")
            self.close_connection = True
            return
        self.rfile = self.connection.makefile(mode='rb')
        self.wfile = self.connection.makefile(mode='wb')
        ret = self.headers.get("Content-Length", "")
        if ret.isdigit():
            self.certtupel = json.loads(str(self.rfile.read(int(ret)), "utf-8")).get("origcertinfo")
        self.send_response(200)
        self.send_header('Connection', 'keep-alive')
        # hack
        self.send_header("Content-Length", "0")
        self.end_headers()
    @functools.lru_cache()
    def webversion(self, page):
        with open(os.path.join(thisdir, "webdata", page), "rb") as ro:
            return ro.read()

    def chat_normal(self, send_type):
        if send_type not in allowed_types:
            self.send_error(400, "invalid type")
            return
        retlen = self.headers.get("Content-Length", "")
        if retlen.isdigit():
            data = self.rfile.read(int(retlen))
            ret = json.loads(str(data, "utf-8"))
            self.send_response(200)
            self.end_headers()
            self.wfile.flush()
            ret["type"] = send_type
            ret["sensitivity"] = 0
            self.notify(writeStuff(self.basedir, self.certtupel[1], ret, False, writedisk=True))
        else:
            self.send_error(411)

    def chat_private(self, send_type):
        if send_type not in allowed_types:
            self.send_error(400, "invalid type")
            return
        retlen = self.headers.get("Content-Length", "")
        if retlen.isdigit():
            data = loadfromsocket(self.connection, int(retlen))
            ret = json.loads(str(data, "utf-8"))
            self.send_response(200)
            self.end_headers()
            self.wfile.flush()
            ret["type"] = send_type
            ret["sensitivity"] = 1
            self.notify(writeStuff(self.basedir, str(self.certtupel[1]), ret, False, writedisk=False))
        else:
            self.send_error(411)

    def chat_sensitive(self, send_type):
        if send_type not in allowed_types:
            self.send_error(400, "invalid type")
            return
        if not self.issensitive():
            self.send_error(400, "counterpart not sensitive")
            return
        retlen = self.headers.get("Content-Length", "")
        if retlen.isdigit():
            data = loadfromsocket(self.connection, int(retlen))
            ret = json.loads(str(data, "utf-8"))
            self.send_response(200)
            self.end_headers()
            self.wfile.flush()
            ret["type"] = send_type
            ret["sensitivity"] = 2
            self.notify(writeStuff(self.basedir, str(self.certtupel[1]), ret, False, writedisk=False))
        else:
            self.send_error(411)

    def send_file(self, fileid: str):
        if not fileid.isdecimal():
            self.send_error(400, "invalid fileid")
            return
        retlen = self.headers.get("Content-Length", "")
        if retlen.isdecimal():
            self.rfile.read(int(retlen))
        entry = messagebuffer.get(self.certtupel[1] , {}).get(int(fileid), None)
        if not entry:
            fjspath = os.path.join(self.basedir, self.certtupel[1], fileid)
            try:
                with open(fjspath, "r") as reob:
                    entry = json.read(reob)
            except Exception:
                self.send_error(404, "File not available")
                return

        if entry.get("type") != "file" or not entry.get("owner"):
            self.send_error(500, "send_file: entry has wrong format")
            return
        path = os.path.exists(entry.get("filepath", ""))
        if not path:
            self.send_error(404, "File was deleted")
            return
        range = self.headers.get("Range", None)
        if range:
            splitrange = range.split("=", 1)
            if len(splitrange) == 1:
                self.send_error(400, "Wrong Range")
                return
            splitrange = range.split("-", 1)
            if len(splitrange) == 1: # (own) shortcut for starting with startaddress
                offset, countbytes = int(splitrange), None
            else:
                offset, countbytes  = int(splitrange[0]), int(splitrange[1])-int(splitrange[0])
        else:
            offset, countbytes = 0, None
        self.send_response(200)
        if countbytes:
            self.send_header("Content-Length", str(countbytes))
        else:
            self.send_header("Content-Length", str(os.stat(path).st_size))
        self.end_headers()
        self.connection.send_file(path, offset, countbytes)

    def do_GET(self):
        if self.path in {"/", "/index"}:
            ob = self.webversion("index.html")
            self.send_response(200)
            self.send_header("Content-Length", str(len(ob)))
            self.end_headers()
            self.wfile.write(ob)
            return

    def do_POST(self):
        if self.path == "/wrapping":
            self.wrap()
            return

        splitted = self.path[1:].split("/", 1)
        if len(splitted) == 2 and splitted[0] in {"chat_normal", "chat_private", "chat_sensitive", "send_file"}:
            action = getattr(self, splitted[0], None)
            action(splitted[1])
        else:
            self.send_error(404)

class httpserver(socketserver.ThreadingMixIn, server.HTTPServer):
    address_family = socket.AF_INET6
    socket_type = socket.SOCK_STREAM

def init(srequester, handler):
    hserver = httpserver(("::1", 0), handler)
    body = {"port": hserver.server_port, "name": "chatscn", "post": True, "wrappedport": True}
    resp = srequester.requester.do_request("/client/registerservice", body, {})
    if not logcheck(resp, logging.ERROR):
        hserver.shutdown()
        return None
    handler.forcehash = resp[3][1]
    threading.Thread(target=hserver.serve_forever, daemon=True).start()
    srequester.requester.p.keywords["forcehash"] = resp[3][1]
    srequester.requester.p.keywords["ownhash"] = resp[3][1]
    return hserver
