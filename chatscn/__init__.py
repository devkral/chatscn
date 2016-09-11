#! /usr/bin/env python3


import threading
import abc
import ssl
import json
import logging
import socket
import functools
import os
import socketserver
import time

from http import server, client
from simplescn.tools import default_sslcont, dhash, scnparse_url
def license():
    print("This software is licensed under MIT-License")
thisdir = os.path.dirname(__file__)

messagebuffer = {}
pathbuffer = {}

simplelock = threading.RLock()
def getticket(path, certhash):
    with simplelock:
        os.makedirs(path, 0o700, exist_ok=True)
        try:
            with open(os.path.join(path, "number"), "rw") as rowob:
                number = int(rowob.read()) + 1
                rowob.seek(0, 0)
                rowob.write(str(number))
                return number
        except:
            with open(os.path.join(path, "number"), "w") as rowob:
                rowob.write("0")
                return 0

def writeBuffer(number,  certhash, newentry):
    with simplelock:
        if certhash not in messagebuffer:
            messagebuffer[certhash] = {}
        messagebuffer[number] = newentry

def writeStuff(path, certhash, dicob, isowner, writedisk=True):
    luckynumber = getticket(os.path.join(path, certhash), certhash)
    dicob["owner"] = isowner
    dicob["time"] = int(time.time())
    dicob["number"] = luckynumber
    if writedisk:
        with open(os.path.join(path, certhash, "{}.json"(luckynumber)), "w") as waffle:
            json.dump(waffle, dicob)
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
    ownaddress = None
    requester = None
    basedir =  None
    def __init__(self, address,  requester, basedir):
        self.ownaddress = address
        self.requester = requester
        self.basedir = basedir
        
    def do_request(self, path, body, headers, **kwargs):
         return self.requester.do_request(self.ownaddress, path, body=body, headers=headers, **kwargs)

    def do_request_simple(self, path, body, headers, **kwargs):
         return self.requester.do_request_simple(self.ownaddress, path, body=body, headers=headers, **kwargs)

    def do_requestdo(self, address: str, path: str, body): #, headers: dict, **kwargs
        body = {"name": "chatscn", "address": address}
        respw = self.do_request("/client/wrap", body, {})
        if not respw[1] or respw[0] is None:
            logging.error(respw[2])
            return None

        con = client.HTTPConnection(*scnparse_url(address))
        con.sock = respw[0].sock
        respw[0].sock = None
        #print("lsls")
        ob = bytes(body,"utf-8")
        con.putrequest("POST", "/chat")
        con.putheader("Content-Length", str(len(ob)))
        con.putheader("Content-Type", "application/json")
        con.endheaders()
        con.send(ob)
        respl = con.getresponse()

        if respl.status != 200:
            logging.error(respl.read())
        return respl

    def send_text(self, address, certhash, sensitivel, text):
        body = {"text": text}
        resp = self.do_requestdo(address, "/chat_{}/text".format(sensitivel), body)
        if resp.status == 200:
            writeStuff(self.basepath, certhash, body, True, writedisk= sensitivel==0)
            return True
        return False

    def send_image(self, address, certhash, pathtofile):
        pass
   
    def send_file(self, address, certhash, filepath):
        pass

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
    for filename  in sorted(os.listdir(basedir)):
        fpath = os.path.join(basedir, filename)
        ret.append(_loadfromdir(fpath, func, data))
    return ret


allowed_types = {"image", "file", "text"}
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
            ret = json.loads(str(self.rfile.read(int(retlen)), "utf-8"))
            ret["type"] = send_type
            ret["sensitivity"] = 0
            self.send_response(200)
            self.end_headers()
            self.notify(writeStuff(self.basedir, str(self.certtupel[1]), ret, False, writedisk=True))
        else:
            self.send_error(411) 

    def chat_private(self, send_type):
        if send_type not in allowed_types:
            self.send_error(400, "invalid type")
            return
        retlen = self.headers.get("Content-Length", "")
        if retlen.isdigit():
            ret = json.loads(str(self.rfile.read(int(retlen)), "utf-8"))
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
            ret = json.loads(str(self.rfile.read(int(retlen)), "utf-8"))
            ret["type"] = send_type
            ret["sensitivity"] = 2
            self.notify(writeStuff(self.basedir, str(self.certtupel[1]), ret, False, writedisk=False))
        else:
            self.send_error(411) 

    def send_file(self, pathid):
        path = pathbuffer.get("".join(pathid, self.certtupel[1]), (None, None))[0]
        if path is None:
            self.send_error(404, "File not available")
            return
        if not os.path.exists(path):
            self.send_error(404, "File not exists")
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

    def do_POST(self):
        if self.path == "/wrapping":
            self.wrap()
            return
        if self.path in {"/", "/index"}:
            ob = self.webversion("index.html")
            self.send_response(200)
            self.send_header("Content-Length", str(len(ob)))
            self.end_headers()
            self.wfile.write(ob)
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
    resp = srequester.do_request("/client/registerservice", body, {})
    if resp[0]:
        resp[0].close()
    if not resp[1]:
        logging.error(resp[2])
        hserver.shutdown()
        return None
    handler.forcehash = resp[3][1]
    threading.Thread(target=hserver.serve_forever, daemon=True).start()
    srequester.requester.saved_kwargs["forcehash"] = resp[3][1]
    srequester.requester.saved_kwargs["ownhash"] = resp[3][1]
    return hserver
