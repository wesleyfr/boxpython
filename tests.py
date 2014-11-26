import unittest
import urlparse
import boxpython
import urllib
import httpretty
import json
import tempfile
import os
import filecmp
from sure import expect

class BoxPythonInteractiveScenarioTest(unittest.TestCase):

    def __get_box_data(self, interactive=True):
        self.data_file = "/tmp/test_data.txt"
        self.token_file = "/tmp/test_token.txt"

        if interactive:
            inputresp = raw_input('Use client id and secret'\
                                    ' from file %s? [y,n]' % self.data_file)

        if interactive and inputresp.lower() != 'y':
            client_id = raw_input('Write your client id :')
            client_secret = raw_input('Write your client secret :')
            self.__save_pair(self.data_file, client_id, client_secret)
        else:
            client_id, client_secret = self.__load_pair(self.data_file)

        if interactive:
            inputresp = raw_input('Use access and refresh token' \
                                    ' from file %s? [y,n]' % self.token_file)

        if interactive and inputresp.lower() != 'y':
            boxflow = boxpython.BoxAuthenticateFlow(client_id, client_secret)
            url = boxflow.get_authorization_url()

            import webbrowser
            webbrowser.open(url)
            auth_code = raw_input('Go to %s and write auth code :' % url)

            access_token, refresh_token = boxflow.get_access_tokens(auth_code)

            self.__save_pair(self.token_file, refresh_token, access_token)
        else:
            refresh_token, access_token = self.__load_pair(self.token_file)

        return client_id, client_secret, refresh_token, access_token

    def __save_pair(self, file, pair1, pair2):
        with open(file, "wt") as f:
            f.write('%s\n' % (pair1,))
            f.write('%s' % (pair2,))

    def __load_pair(self, file):
        with open(file, "rt") as f:
            lines = f.read().splitlines()
            return lines[0], lines[1]

    def __new_tokens_callback(self, refresh_token, access_token):
        self.__save_pair(self.token_file, refresh_token, access_token)

    def run_big_file_senario(self):

        (client_id, client_secret,
        refresh_token, access_token) = self.__get_box_data(interactive=True)

        box = boxpython.BoxSession(client_id, client_secret,
                                    refresh_token, access_token,
                                    self.__new_tokens_callback)

        folder_id = self.__create_boxpython_test_folder(box);

        self.passed_in_progress_callback = False
        my_file_content2 = os.urandom(1024*1024*1) #1 MO
        my_file2 =  self.__create_file(my_file_content2,
                                            "/tmp/test_big_file.bin")
        try:
            resp = box.chunk_upload_file("test_big_file.bin",
                        folder_id, my_file2,
                        progress_callback=self.__progress_callback,
                        chunk_size=int(len(my_file_content2)/10.0))
            my_file2_id = int(resp['entries'][0]['id'])
            self.assertTrue(self.passed_in_progress_callback)

            self.passed_in_progress_callback = False
            try:
                my_file2_dl = my_file2 + 'dl'
                resp = box.download_file(my_file2_id, my_file2_dl,
                                    progress_callback=self.__progress_callback,
                                    chunk_size=int(len(my_file_content2)/10.0))

                self.assertTrue(filecmp.cmp(my_file2, my_file2_dl))
                self.assertTrue(self.passed_in_progress_callback)
            finally:
                os.remove(my_file2_dl)
        finally:
            os.remove(my_file2)


    def __create_boxpython_test_folder(self, box):
        try:
            resp = box.create_folder("boxpython_test_folder")
        except boxpython.BoxError, ex:
            if ex.status != 409:
                raise
            folder_id = box.find_id_in_folder("boxpython_test_folder")
            box.delete_folder(folder_id)
            resp = box.create_folder("boxpython_test_folder")

        return int(resp['id'])

    def run_full_scenario(self):

        (client_id, client_secret,
        refresh_token, access_token) = self.__get_box_data(interactive=True)

        box = boxpython.BoxSession(client_id, client_secret,
                                    refresh_token, access_token,
                                    self.__new_tokens_callback)


        box.get_folder_info(0)

        folder_id = self.__create_boxpython_test_folder(box);

        resp = box.get_user_info()
        self.assertTrue('login' in resp)
        self.assertTrue('job_title' in resp)
        self.assertTrue('avatar_url' in resp)

        resp = box.get_folder_items(folder_id)
        self.assertEqual(resp, {u'total_count': 0, u'offset': 0, u'limit': 100, u'order': [{u'direction': u'ASC', u'by': u'type'}, {u'direction': u'ASC', u'by': u'name'}], u'entries': []})

        resp = box.get_folder_items(folder_id, limit=1000, offset=2)
        self.assertEqual(resp, {u'total_count': 0, u'offset': 2, u'limit': 1000, u'order': [{u'direction': u'ASC', u'by': u'type'}, {u'direction': u'ASC', u'by': u'name'}], u'entries': []})

        resp = box.get_folder_items(folder_id, limit=1000, offset=2,
                                        fields_list=['name', 'created_at'])
        self.assertEqual(resp, {u'total_count': 0, u'offset': 2, u'limit': 1000, u'order': [{u'direction': u'ASC', u'by': u'type'}, {u'direction': u'ASC', u'by': u'name'}], u'entries': []})

        resp = box.create_folder("new_folder", folder_id)
        new_folder = int(resp['id'])

        resp = box.get_folder_items(folder_id)
        self.assertEqual(resp['total_count'], 1)
        self.assertEqual(int(resp['entries'][0]['id']), new_folder)

        my_file_content1 = "content of my file"
        my_file1 = self.__create_file(my_file_content1)
        try:
            resp = box.upload_file("my_file1.txt", new_folder, my_file1)
            my_file1_id = int(resp['entries'][0]['id'])
        finally:
            os.remove(my_file1)

        resp = box.get_file_info(my_file1_id)
        self.assertEqual(resp['name'], "my_file1.txt")

        box.delete_file(my_file1_id)

        with self.assertRaises(boxpython.BoxError) as cm:
            box.get_file_info(my_file1_id)


        my_file_content1 = "content of my file "*20
        my_file1 = self.__create_file(my_file_content1)
        try:
            resp = box.upload_file("my_file1.txt", new_folder, my_file1)
            my_file1_id = int(resp['entries'][0]['id'])
        finally:
            os.remove(my_file1)

        self.passed_in_progress_callback = False
        my_file_content2 = os.urandom(1024*1024*1) #1 MO
        my_file2 = self.__create_file(my_file_content2)
        try:
            resp = box.chunk_upload_file("my_file2.txt", new_folder, my_file2,
                    progress_callback=self.__progress_callback)
            my_file2_id = int(resp['entries'][0]['id'])
        finally:
            os.remove(my_file2)
        self.assertTrue(self.passed_in_progress_callback)

        self.passed_in_progress_callback = False
        my_file_content3 = b''
        my_file3 = self.__create_file(my_file_content3)
        try:
            resp = box.chunk_upload_file("my_file3.txt", new_folder, my_file3,
                    progress_callback=self.__progress_callback)
            my_file3_id = int(resp['entries'][0]['id'])
        finally:
            os.remove(my_file3)
        self.assertTrue(self.passed_in_progress_callback)

        self.passed_in_progress_callback = False
        my_file_content4 = b''
        my_file4 = self.__create_file(my_file_content4)
        try:
            resp = box.chunk_upload_file("my_file4.txt", new_folder, my_file4,
                    progress_callback=self.__progress_callback)
            my_file4_id = int(resp['entries'][0]['id'])
        finally:
            os.remove(my_file4)
        self.assertTrue(self.passed_in_progress_callback)

        to_check = [(my_file1_id, my_file_content1),
                    (my_file2_id, my_file_content2),
                    (my_file3_id, my_file_content3),
                    (my_file4_id, my_file_content4)
                    ]

        for curr_check in to_check:
            my_testfile = self.__create_file(b'')
            try:
                resp = box.download_file(curr_check[0], my_testfile,
                            progress_callback=self.__progress_callback)
                self.assertEqual(self.__get_file_content(my_testfile),
                                        curr_check[1])
            finally:
                os.remove(my_testfile)


        search_result = box.search(query="boxpython_test_folder")

        self.assertTrue(search_result["entries"] is not None)
        # Sometimes, it takes a little bit of time for the search indexes to be
        # updated with the new file/folder metadata. So we do not check values.
        #self.assertEqual(folder_id, search_result['entries'][0]['id'])

        resp = box.delete_folder(folder_id)



    def __progress_callback(self, transferred, total):
        #print 'progress_callback = %s/%s' % (transferred, total, )
        self.passed_in_progress_callback = True

    def __get_file_content(self, file_path):
        with open(file_path) as f:
            return f.read()

    def __create_file(self, content, force_file_path=None):
        if force_file_path:
            f = open(force_file_path, "w")
        else:
            f = tempfile.NamedTemporaryFile(delete=False)
        f.write(content)
        f.close()
        return f.name


class BoxPythonUnitTest(unittest.TestCase):

    def setUp(self):
        self.client_id = 'client_id_code'
        self.client_secret = 'client_secret_code'
        self.refresh_token = None
        self.access_token = None

    @httpretty.activate
    def test_create_boxsession(self):
        body = {    "access_token": "T9cE5asGnuyYCCqIZFoWjFHvNbvVqHjl",
                    "expires_in": 3600,
                    "restricted_to": [],
                    "token_type": "bearer",
                    "refresh_token": "new_refresh_token!!" }

        httpretty.register_uri(httpretty.POST,
                                "https://www.box.com/api/oauth2/token",
                                body=json.dumps(body),
                                status=200,
                                content_type='text/json')

        refresh_token = "refresh_token_dummy#!"
        box = boxpython.BoxSession(self.client_id, self.client_secret,
                                    refresh_token, last_access_token=None)

        query_body = httpretty.last_request().body

        self.assertEqual(urlparse.parse_qs(query_body),
            {   "client_id": [self.client_id],
                "client_secret": [self.client_secret],
                "grant_type": ["refresh_token"],
                "refresh_token": [refresh_token],})

        self.assertEqual(body['refresh_token'], box.refresh_token)
        self.assertEqual(body['access_token'], box.access_token)

    @httpretty.activate
    def test_create_boxsession_no_refresh_token(self):

        refresh_token = "refresh_token_dummy#!"
        access_token = "access_token_dummy#!"
        boxpython.BoxSession(self.client_id, self.client_secret,
                                    refresh_token, access_token)

        self.assertIsInstance(httpretty.httpretty.last_request,
                                  httpretty.core.HTTPrettyRequestEmpty)

    @httpretty.activate
    def test_get_folder_info(self):
        folder_id = 165
        body = get_dummy_folder_result()
        body['id'] = folder_id

        httpretty.register_uri(httpretty.GET,
                        "https://api.box.com/2.0/folders/%s" % folder_id,
                        body=json.dumps(body),
                        status=200,
                        content_type='text/json')

        refresh_token = "refresh_token_dummy#!"
        access_token = "access_token_dummy#!"
        box = boxpython.BoxSession(self.client_id, self.client_secret,
                                    refresh_token, access_token)

        resp = box.get_folder_info(folder_id)

        expect(httpretty.last_request()).have.property("querystring").\
                    should.be.equal({})

        expect(httpretty.last_request()).have.property("body").\
                    should.be.equal('')

        expect(httpretty.last_request().headers['Authorization']).\
                    to.equal('Bearer %s' % access_token)

        (resp).should.be.equal(body)


    @httpretty.activate
    def test_get_folder_info_with_expired_access_token(self):
        body_token = {"access_token": "T9cE5asGnuyYCCqIZFoWjFHvNbvVqHjl",
                    "expires_in": 3600,
                    "restricted_to": [],
                    "token_type": "bearer",
                    "refresh_token": "new_refresh_token!!" }

        httpretty.register_uri(httpretty.POST,
                "https://www.box.com/api/oauth2/token",
                body=json.dumps(body_token),
                status=200,
                content_type='text/json')

        folder_id = 168
        body = get_dummy_folder_result()
        body['id'] = folder_id

        httpretty.register_uri(httpretty.GET,
                "https://api.box.com/2.0/folders/%s" % folder_id,
                responses=[
                    httpretty.Response(body=json.dumps({}), status=401),
                    httpretty.Response(body=json.dumps(body), status=200),
                ])

        refresh_token = "refresh_token_dummy expired #!"
        access_token = "access_token_dummy expired #!"
        box = boxpython.BoxSession(self.client_id, self.client_secret,
                                    refresh_token, access_token)

        resp = box.get_folder_info(folder_id)

        (resp).should.be.equal(body)


    @httpretty.activate
    def test_get_folder_info_with_expired_refresh_token(self):
        body_token = {"access_token": "T9cE5asGnuyYCCqIZFoWjFHvNbvVqHjl",
                    "expires_in": 3600,
                    "restricted_to": [],
                    "token_type": "bearer",
                    "refresh_token": "new_refresh_token!!" }

        httpretty.register_uri(httpretty.POST,
                "https://www.box.com/api/oauth2/token",
                body=json.dumps(body_token),
                status=200,
                content_type='text/json')

        folder_id = 168
        body = get_dummy_folder_result()
        body['id'] = folder_id

        httpretty.register_uri(httpretty.GET,
                "https://api.box.com/2.0/folders/%s" % folder_id,
                responses=[
                    httpretty.Response(body=json.dumps({}), status=401),
                    httpretty.Response(body=json.dumps({}), status=401),
                ])

        refresh_token = "refresh_token_dummy expired #!"
        access_token = "access_token_dummy expired #!"
        box = boxpython.BoxSession(self.client_id, self.client_secret,
                                    refresh_token, access_token)

        with self.assertRaises(boxpython.BoxError) as cm:
            resp = box.get_folder_info(folder_id)

        self.assertEqual(cm.exception.status, 401)

    @httpretty.activate
    def test_search(self):
        body_token = {"access_token": "T9cE5asGnuyYCCqIZFoWjFHvNbvVqHjl",
                    "expires_in": 3600,
                    "restricted_to": [],
                    "token_type": "bearer",
                    "refresh_token": "new_refresh_token!!" }

        httpretty.register_uri(httpretty.POST,
                "https://www.box.com/api/oauth2/token",
                body=json.dumps(body_token),
                status=200,
                content_type='text/json')
        folder_id = 168
        body = get_dummy_search_result()
        body["entries"][0]['id'] = folder_id

        httpretty.register_uri(httpretty.GET,
                        "https://api.box.com/2.0/search?query=Empowering",
                        body=json.dumps(body),
                        status=200,
                        match_querystring=True,
                        content_type='application/json')
        refresh_token = "T9cE5asGnuyYCCqIZFoWjFHvNbvVqHjl"
        access_token = "new_refresh_token!!"
        box = boxpython.BoxSession(self.client_id, self.client_secret,
                                    refresh_token, access_token)

        search_result = box.search(query="Empowering")
        self.assertTrue(search_result["entries"] is not None)
        self.assertEqual(folder_id,search_result["entries"][0]["id"])



class BoxAuthenticateFlowUnitTest(unittest.TestCase):
    def setUp(self):
        self.client_id = 'client_id_code'
        self.client_secret = 'client_secret_code'

    def test_get_authorization_url(self):
        b = boxpython.BoxAuthenticateFlow(self.client_id, self.client_secret)
        url = b.get_authorization_url()

        (scheme,
            netloc,
            path,
            params,
            query,
            fragment) = urlparse.urlparse(url)

        expected = ('https', 'www.box.com', '/api/oauth2/authorize', '', '')
        returned = (scheme, netloc, path, params, fragment)
        self.assertEqual(returned, expected)

        query_dict = urlparse.parse_qs(query)
        self.assertEqual(query_dict['client_id'], [self.client_id])
        self.assertEqual(query_dict['response_type'], ['code'])
        self.assertEqual(query_dict['state'], ['authenticated'])

    def test_get_authorization_url_redirect(self):
        b = boxpython.BoxAuthenticateFlow(self.client_id, self.client_secret)
        redirect_uri = 'http://toto.com/123?4&a=%201'
        url = b.get_authorization_url(redirect_uri)

        (scheme,
            netloc,
            path,
            params,
            query,
            fragment) = urlparse.urlparse(url)

        query_dict = urlparse.parse_qs(query)
        decoded_uri = urllib.unquote_plus(query_dict['redirect_uri'][0])
        redirect_uri = urllib.unquote_plus(redirect_uri)
        self.assertEqual(decoded_uri, redirect_uri)

    @httpretty.activate
    def test_get_access_tokens(self):
        body = {    "access_token": "T9cE5asGnuyYCCqIZFoWjFHvNbvVqHjl",
                    "expires_in": 3600,
                    "restricted_to": [],
                    "token_type": "bearer",
                    "refresh_token": "J7rxTiWOHMoSC1isKZKBZWizoRXjkQzig5C6jFgCVJ9bUnsUfGMinKBDLZWP9BgR" }

        httpretty.register_uri(httpretty.POST,
                                "https://www.box.com/api/oauth2/token",
                                body=json.dumps(body),
                                status=200,
                                content_type='text/json')

        b = boxpython.BoxAuthenticateFlow(self.client_id, self.client_secret)
        auth_code = "@#$@FEWR"
        access_token, refresh_token = b.get_access_tokens(auth_code)

        self.assertEqual(access_token, body['access_token'])
        self.assertEqual(refresh_token, body['refresh_token'])

        query_body = httpretty.last_request().body

        self.assertEqual(urlparse.parse_qs(query_body),
            {   "client_id": [self.client_id],
                "client_secret": [self.client_secret],
                "grant_type": ["authorization_code"],
                "code": [auth_code],})


    @httpretty.activate
    def test_get_access_tokens_with_box_error(self):
        body = {    "error": "invalid_grant",
                    "error_description": "Invalid user credentials" }

        httpretty.register_uri(httpretty.POST,
                                "https://www.box.com/api/oauth2/token",
                                body=json.dumps(body),
                                status=401,
                                content_type='text/json')

        b = boxpython.BoxAuthenticateFlow(self.client_id, self.client_secret)
        auth_code = "@#$@FEWR"
        with self.assertRaises(boxpython.BoxError) as cm:
            access_token, refresh_token = b.get_access_tokens(auth_code)

        self.assertEqual(cm.exception.status, 401)

    @httpretty.activate
    def test_get_access_tokens_with_json_error(self):
        body = {    "error": "invalid_grant",
                    "error_description": "Invalid user credentials" }

        httpretty.register_uri(httpretty.POST,
                                "https://www.box.com/api/oauth2/token",
                                body="{xyz#",
                                status=200,
                                content_type='text/json')

        b = boxpython.BoxAuthenticateFlow(self.client_id, self.client_secret)
        auth_code = "@#$@FEWR"
        with self.assertRaises(boxpython.BoxHttpResponseError):
            access_token, refresh_token = b.get_access_tokens(auth_code)


def get_dummy_folder_result():
    return {"type": "folder",
            "id": "11446498",
            "sequence_id": "1",
            "etag": "1",
            "name": "Pictures",
            "created_at": "2012-12-12T10:53:43-08:00",
            "modified_at": "2012-12-12T11:15:04-08:00",
            "description": "Some pictures I took",
            "size": 629644,
            "path_collection": {
                "total_count": 1,
                "entries": [
                    {
                        "type": "folder",
                        "id": "0",
                        "sequence_id": None,
                        "etag": None,
                        "name": "All Files"
                    }
                ]
            },
            "created_by": {
                "type": "user",
                "id": "17738362",
                "name": "sean rose",
                "login": "sean@box.com"
            },
            "modified_by": {
                "type": "user",
                "id": "17738362",
                "name": "sean rose",
                "login": "sean@box.com"
            },
            "owned_by": {
                "type": "user",
                "id": "17738362",
                "name": "sean rose",
                "login": "sean@box.com"
            },
            "shared_link": {
                "url": "https://www.box.com/s/vspke7y05sb214wjokpk",
                "download_url": "https://www.box.com/shared/static/vspke7y05sb214wjokpk",
                "vanity_url": None,
                "is_password_enabled": False,
                "unshared_at": None,
                "download_count": 0,
                "preview_count": 0,
                "access": "open",
                "permissions": {
                    "can_download": True,
                    "can_preview": True
                }
            },
            "folder_upload_email": {
                "access": "open",
                "email": "upload.Picture.k13sdz1@u.box.com"
            },
            "parent": {
                "type": "folder",
                "id": "0",
                "sequence_id": None,
                "etag": None,
                "name": "All Files"
            },
            "item_status": "active",
            "item_collection": {
                "total_count": 1,
                "entries": [
                    {
                        "type": "file",
                        "id": "5000948880",
                        "sequence_id": "3",
                        "etag": "3",
                        "sha1": "134b65991ed521fcfe4724b7d814ab8ded5185dc",
                        "name": "tigers.jpeg"
                    }
                ],
                "offset": 0,
                "limit": 100
            }
        }

def get_dummy_search_result():
    return {
        "total_count": 1,
        "entries": [
            {
                "type": "file",
                "id": "172245607",
                "sequence_id": "1",
                "etag": "1",
                "sha1": "f89d97c5eea0a68e2cec911s932eca34a52355d2",
                "name": "Box for Sales - Empowering Your Mobile Worker White paper 2pg (External).pdf",
                "description": "This is old and needs to be updated - but general themes still apply",
                "size": 408979,
                "path_collection": {
                    "total_count": 2,
                    "entries": [
                        {
                            "type": "folder",
                            "id": "0",
                            "sequence_id": None,
                            "etag": None,
                            "name": "All Files"
                        },
                        {
                            "type": "folder",
                            "id": "2150506",
                            "sequence_id": "1",
                            "etag": "1",
                            "name": "Marketing Active Work"
                        }
             ]
                },
                "created_at": "2014-05-17T12:59:45-07:00",
                "modified_at": "2014-05-17T13:00:20-07:00",
                "trashed_at": None,
                "purged_at": None,
                "content_created_at": "2014-05-17T12:58:58-07:00",
                "content_modified_at": "2014-05-17T12:58:58-07:00",
                "created_by": {
                    "type": "user",
                    "id": "19551097",
                    "name": "Ted Blosser",
                    "login": "ted@box.com"
                },
                "modified_by": {
                    "type": "user",
                    "id": "19551097",
                    "name": "Ted Blosser",
                    "login": "ted@box.com"
                },
                "owned_by": {
                    "type": "user",
                    "id": "19551097",
                    "name": "Ted Blosser",
                    "login": "ted@box.com"
                },
                "shared_link": None,
                "parent": {
                            "type": "folder",
                            "id": "2150506",
                            "sequence_id": "1",
                            "etag": "1",
                            "name": "Marketing Active Work"
                },
                "item_status": "active"
            }
        ],
        "limit": 30,
        "offset": 0
    }

if __name__ == '__main__':
    unittest.main()
