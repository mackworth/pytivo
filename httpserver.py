import time, os, BaseHTTPServer, SocketServer, socket, shutil, os.path
from urllib import unquote_plus, quote, unquote
from urlparse import urlparse
from xml.sax.saxutils import escape
from cgi import parse_qs
from Cheetah.Template import Template
import transcode

SCRIPTDIR = os.path.dirname(__file__)

class TivoHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    containers = {}
    
    def __init__(self, server_address, RequestHandlerClass):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)
        self.daemon_threads = True

    def add_container(self, name, type, path):
        if self.containers.has_key(name) or name == 'TivoConnect':
            raise "Container Name in use"
        self.containers[name] = {'type' : type, 'path' : path}

class TivoHTTPHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
      
        for name, container in self.server.containers.items():
            #XXX make a regex
            if self.path.startswith('/' + name):
                self.send_static(name, container)
                return
        
        if not self.path.startswith('/TiVoConnect'):
            self.infopage()
            return
        
        o = urlparse("http://fake.host" + self.path)
        query = parse_qs(o.query)

        mname = False
        if query.has_key('Command') and len(query['Command']) >= 1:
            mname = 'do_' + query['Command'][0]
        if mname and hasattr(self, mname):
            method = getattr(self, mname)
            method(query)
        else:
            self.unsuported(query)
            
    def do_QueryContainer(self, query):
        
        if not query.has_key('Container'):
            query['Container'] = ['/']
        self.send_response(200)
        self.end_headers()
        if query['Container'][0] == '/':
            t = Template(file=os.path.join(SCRIPTDIR, 'templates', 'root_container.tmpl'))
            t.containers = self.server.containers
            t.hostname = socket.gethostname()
            self.wfile.write(t)
        else:
            
            subcname = query['Container'][0]
            cname = subcname.split('/')[0]
             
            if not self.server.containers.has_key(cname):
                return
            
            container = self.server.containers[cname]

            folders = subcname.split('/')
            path = container['path']
            for folder in folders[1:]:
                if folder == '..':
                    return
                path = os.path.join(path, folder)
           

            files = os.listdir(path)

            files = filter(lambda f: os.path.isdir(os.path.join(path, f)) or transcode.suported_format(os.path.join(path,f)), files)
            
            totalFiles = len(files)
 
            def isdir(file):
                return os.path.isdir(os.path.join(path, file))                     

            index = 0
            if query.has_key('ItemCount'):
                count = int(query['ItemCount'] [0])
                
                if query.has_key('AnchorItem'):
                    anchor = unquote(query['AnchorItem'][0])
                    print anchor
                    for i in range(len(files)):
                        
                        if isdir(files[i]):
                            file_url = '/TiVoConnect?Command=QueryContainer&Container=' + subcname + '/' + files[i]
                        else:                                
                            file_url = '/' + subcname + '/' + files[i]
                        if file_url == anchor:
                            index = i + 1
                            break
                if query.has_key('AnchorOffset'):
                    index = index +  int(query['AnchorOffset'][0])
                files = files[index:index + count]
           

            
            t = Template(file=os.path.join(SCRIPTDIR,'templates', 'container.tmpl'))
            t.name = subcname
            t.files = files
            t.total = totalFiles
            t.start = index
            t.isdir = isdir
            t.quote = quote
            t.escape = escape
            self.wfile.write(t)

    def send_static(self, name, container):

        #cheep hack 
        if self.headers.getheader('Range') and not self.headers.getheader('Range') == 'bytes=0-':
            self.send_response(404)
            self.end_headers()
            return
        
        o = urlparse("http://fake.host" + self.path)
        path = unquote_plus(o.path)
        self.send_response(200)
        self.end_headers()
        transcode.output_video(container['path'] + path[len(name)+1:], self.wfile)
    
    def infopage(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR, 'templates', 'info_page.tmpl'))
        self.wfile.write(t)
        self.end_headers()

    def unsuported(self, query):
        self.send_response(404)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates','unsuported.tmpl'))
        t.query = query
        self.wfile.write(t)
       
if __name__ == '__main__':
    def start_server():
        httpd = TivoHTTPServer(('', 9032), TivoHTTPHandler)
        httpd.add_container('test', 'x-container/tivo-videos', r'C:\Documents and Settings\Armooo\Desktop\pyTivo\test')
        httpd.serve_forever()

    start_server()