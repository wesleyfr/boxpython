import requests
import urllib
import json

class BoxRestRequest(object):

    AUTH_PREFIX = "https://www.box.com/api"
    API_PREFIX = "https://api.box.com/2.0"
    API_UPLOAD_PREFIX = "https://upload.box.com/api/2.0"

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None

        self.requests_func = {  "GET": requests.get,
                                "POST": requests.post,
                                "PUT": requests.put,
                                "DELETE": requests.delete, }

    def get_authorization_url(self, redirect_uri=None):
        url = '%s/oauth2/authorize?response_type=code' \
                '&client_id=%s&state=authenticated' % \
                    (BoxRestRequest.AUTH_PREFIX, self.client_id)

        if redirect_uri:
            url += "&redirect_uri=%s" % urllib.quote_plus(redirect_uri)

        return url

    def get_access_token(self, authorization_code, redirect_uri=None):
        url = '%s/oauth2/token' % BoxRestRequest.AUTH_PREFIX
        params = { 'grant_type': 'authorization_code',
                    'code': authorization_code,
                    'client_id': self.client_id,
                    'client_secret': self.client_secret }
        if redirect_uri:
            params['redirect_uri'] = redirect_uri
        return requests.post(url, data=params)

    def refresh_access_token(self, refresh_token):
        url = '%s/oauth2/token' % BoxRestRequest.AUTH_PREFIX
        params = { 'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': self.client_id,
                    'client_secret': self.client_secret }

        return requests.post(url, data=params)

    def request(self, method,
                    command, data=None, querystring=None, files=None, headers=None, stream=None, json_data=True):
        if files:
            url_prefix = BoxRestRequest.API_UPLOAD_PREFIX
        else:
            url_prefix = BoxRestRequest.API_PREFIX

        if headers is None:
            headers = {}
        headers['Authorization'] = 'Bearer %s' % self.access_token

        url = '%s/%s' % (url_prefix, command)

        if json_data:
            data = json.dumps(data)

        kwargs = { 'headers' : headers }
        if data is not None: kwargs['data'] = data
        if querystring is not None: kwargs['params'] = querystring
        if files is not None: kwargs['files'] = files
        if stream is not None: kwargs['stream'] = stream

        return self.requests_func[method](url, **kwargs)

