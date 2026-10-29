"""Open this version on an available port, avoiding an older app on port 8080."""
import threading,webbrowser
import app
app.init()
server=None
for port in range(8082,8092):
    try:server=app.ThreadingHTTPServer(('127.0.0.1',port),app.Handler);break
    except OSError:continue
if server is None:raise SystemExit('No free port from 8082–8091. Stop an older server and try again.')
url=f'http://127.0.0.1:{server.server_port}'
print('WealthDesk DEMO · multiple portfolios',flush=True)
print(url,flush=True)
threading.Timer(.5,lambda:webbrowser.open(url)).start()
try:server.serve_forever()
except KeyboardInterrupt:server.server_close()
