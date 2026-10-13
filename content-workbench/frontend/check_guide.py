import urllib.request
try:
    resp = urllib.request.urlopen('http://localhost:5174/user-guide.html')
    print(resp.getcode())
except Exception as e:
    print('ERROR', e)
