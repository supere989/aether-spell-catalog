import argparse,json,sqlite3,threading,re,subprocess
from functools import lru_cache
from asset_io import png
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from gear_catalog import search_sets,set_detail,search_items
from simulation import CLASSES,simulate
from class_mechanics import kit
BASE=Path(__file__).resolve().parent
GATE=threading.BoundedSemaphore(2)
@lru_cache(maxsize=1)
def visuals():return json.loads((BASE/'assets/visuals.json').read_text())
MODEL_GATE=threading.Lock()
@lru_cache(maxsize=1)
def item_models():
    result={}
    def visit(v):
        if isinstance(v,dict):
            if 'model' in v and 'skin' in v:result[v['model']]=v['skin']
            else:
                for x in v.values():visit(x)
        elif isinstance(v,list):
            for x in v:visit(x)
    for d in visuals()['displays'].values():visit(d.get('attachments',{}))
    return result
class Handler(BaseHTTPRequestHandler):
    def send(self,code,data,kind='application/json'):
        if kind=='application/json':data=json.dumps(data).encode()
        prefix=getattr(self.server,'base_path','')
        if prefix and kind in ('application/json','text/html','text/javascript','application/octet-stream'):
            data=re.sub(rb'''(["'`])/(api/|assets/|models/|vendor/|viewer\.js|app\.js|sets\.js|character\.js|style\.css)''',lambda m:m[1]+prefix.encode()+b'/'+m[2],data)
        self.send_response(code);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(data)))
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.end_headers()
        if self.command!='HEAD':self.wfile.write(data)
    def route(self):
        prefix=getattr(self.server,'base_path','')
        if prefix:
            if not self.path.startswith(prefix+'/'):return False
            self.path=self.path[len(prefix):]
        return True
    def do_HEAD(self):
        self.do_GET()
    def do_GET(self):
        if not self.route():return self.send(404,{'error':'Not found'})
        path=self.path.split('?')[0]
        if path=='/api/item-model':
            identity=parse_qs(urlsplit(self.path).query).get('id',[''])[0];skin=item_models().get(identity)
            if not skin:return self.send(404,{'error':'Unknown item model'})
            try:
                with MODEL_GATE:
                    file=BASE/'assets/item-models-v2'/(identity+'.json')
                    if not file.exists():
                        subprocess.run([str(BASE/'.asset-venv/bin/python'),'-B',str(BASE/'export_item_mesh.py'),identity,skin],check=True,capture_output=True,timeout=30)
                return self.send(200,file.read_bytes(),'application/octet-stream')
            except (OSError,subprocess.SubprocessError):return self.send(422,{'error':'Item model could not be converted'})
        if path=='/api/visuals':return self.send(200,visuals())
        if re.fullmatch(r'/assets/[a-f0-9]{32}\.png',path):
            try:return self.send(200,png(path[8:-4]).read_bytes(),'image/png')
            except (ValueError,OSError):return self.send(404,{'error':'Texture unavailable'})
        if re.fullmatch(r'/models/[0-9]{1,2}-[01]\.json',path):
            file=BASE/'assets/models'/path.rsplit('/',1)[1]
            if file.is_file():return self.send(200,file.read_bytes(),'application/octet-stream')
        if path in ('/vendor/three.module.js','/vendor/three.core.js','/vendor/OrbitControls.js','/viewer.js'):
            return self.send(200,(BASE/'static'/path.lstrip('/')).read_bytes(),'text/javascript')
        if path in ('/api/gear-sets' ,'/api/gear-set'):
            try:
                params=parse_qs(urlsplit(self.path).query)
                if path=='/api/gear-set':
                    detail=set_detail(int(params.get('id',['0'])[0]));v=visuals()
                    detail['items']=[dict(i,icon=v['displays'].get(v['items'].get(str(i['id'])),{}).get('icon')) for i in detail['items']]
                    return self.send(200,detail)
                return self.send(200,search_sets(params.get('q',[''])[0][:100],max(0,int(params.get('offset',['0'])[0])),params.get('stats',['0'])[0]=='1'))
            except (ValueError,TypeError):return self.send(400,{'error':'Invalid set query'})
        if path=='/api/gear-items':
            try:
                p=parse_qs(urlsplit(self.path).query)
                data=search_items(p.get('slot',[''])[0],int(p.get('class',['0'])[0]),int(p.get('level',['0'])[0]),p.get('q',[''])[0][:100],int(p.get('offset',['0'])[0]))
                v=visuals();data['items']=[dict(i,icon=v['displays'].get(v['items'].get(str(i['id'])),{}).get('icon')) for i in data['items']]
                return self.send(200,data)
            except (ValueError,TypeError):return self.send(400,{'error':'Invalid equipment query'})
        if path=='/api/classes':
            c=sqlite3.connect((BASE.parent/'catalog.sqlite').as_uri()+'?mode=ro',uri=True)
            try:
                rows=[{'id':i,'name':name,'catalog_abilities':[{'id':r[0],'name':r[1]} for r in c.execute('SELECT DISTINCT s.id,s.name FROM acquisitions a JOIN spell_index s ON s.id=a.spell_id WHERE a.class_id=? ORDER BY s.level,s.id LIMIT 30',(i,))]} for i,name in enumerate(CLASSES,12)]
            finally:c.close()
            return self.send(200,rows)
        files={'/':('index.html','text/html'),'/sets.js':('sets.js','text/javascript'),'/character.js':('character.js','text/javascript'),'/app.js':('app.js','text/javascript'),'/style.css':('style.css','text/css')}
        if path not in files:return self.send(404,{'error':'Not found'})
        name,kind=files[path];self.send(200,(BASE/'static'/name).read_bytes(),kind)
    def do_POST(self):
        if not self.route():return self.send(404,{'error':'Not found'})
        if self.path not in ('/api/simulate','/api/kit'):return self.send(404,{'error':'Not found'})
        if self.headers.get('Origin') not in (None,f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}',getattr(self.server,'public_origin',None)):
            return self.send(403,{'error':'Origin not allowed'})
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<=1000000:raise ValueError('Invalid request size')
            config=json.loads(self.rfile.read(n))
            if not isinstance(config,dict):raise ValueError('Expected a scenario object')
        except (ValueError,TypeError):return self.send(400,{'error':'Invalid scenario JSON'})
        if not GATE.acquire(blocking=False):return self.send(429,{'error':'Two simulations are already running'})
        try:self.send(200,kit(config) if self.path=='/api/kit' else simulate(config))
        except (ValueError,TypeError,KeyError,AttributeError) as e:self.send(400,{'error':str(e)})
        finally:GATE.release()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8787);p.add_argument('--base-path',default='');p.add_argument('--public-origin');args=p.parse_args()
    if args.base_path and not re.fullmatch(r'/[a-zA-Z0-9_-]+',args.base_path):p.error('Invalid base path')
    print(f'Combat Lab: http://127.0.0.1:{args.port}',flush=True)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    server.base_path=args.base_path;server.public_origin=args.public_origin
    server.serve_forever()
