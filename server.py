#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

from http.server import HTTPServer, CGIHTTPRequestHandler, _url_collapse_path
import serverConfig

class Handler(CGIHTTPRequestHandler):
    def is_cgi(self):
      collapsed_path = _url_collapse_path(self.path)
      split_path = collapsed_path.split('/')
      print(split_path)
      for component in split_path:
            if not component: continue
            elif component == 'static': return False
            else: break
      else:
            self.cgi_info = '','muttsScrape.py'
            return True

httpd = HTTPServer((serverConfig.hostname, serverConfig.port), Handler)
print('serving from ',serverConfig.hostname,':',serverConfig.port,sep='');
httpd.serve_forever()