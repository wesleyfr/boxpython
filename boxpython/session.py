from .request import BoxRestRequest
from .upload import MultipartUploadWrapper
from .exceptions import BoxError, BoxHttpResponseError


class BoxSession(object):
    """Manage files and folder from Box.

    When you instanciate this class you have to provide at least the Refresh Token (found with :class:`BoxAuthenticateFlow`). If the Access Token is not provided a request will be made to Box to get a new one (and a new Refresh Token will be generated).

    The Access Token expires every hour. When you use this class with an Access Token expired, a new one will be requested automatically.

    Use the "tokens_changed" callback to backup the Access Token and the Refresh Token each time they change. If you do not backup them, you will have to follow the authenticate flow again (with :class:`BoxAuthenticateFlow`).

    Usage:
        >>> def tokens_changed(refresh_token, access_token):
        ...    save_to_file(refresh_token, access_token)
        ...
        >>> box = BoxSession('my_id', 'my_secret', refresh_token, access_token, tokens_changed)
        >>> print box.get_folder_info(0)

    """
    def __init__(self, client_id, client_secret,
                    last_refresh_token,
                    last_access_token=None,
                    tokens_changed=None):
        """Constructor

        Args:
            client_id (str): Client ID provided by Box.

            client_secret (str): Client Secret provided by Box.

            last_refresh_token (str): Refresh Token found with the class :class:`BoxAuthenticateFlow`.

            last_access_token (str): Access Token found with the class :class:`BoxAuthenticateFlow`. If None, a new Access Token will be requested to Box.

            tokens_changed (func): Function called each time the Refresh Token and the Access Token is refreshed (because of expiration). Use this to backup your Refresh Token and the Access Token in order to reuse this class without using :class:`BoxAuthenticateFlow` class for getting tokens.

        Raises:
            BoxError: An error response is returned from Box (status_code >= 400).

            BoxHttpResponseError: Response from Box is malformed.

            requests.exceptions.*: Any connection related problem.

        """
        self.box_request = BoxRestRequest(client_id, client_secret)
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = last_refresh_token
        self.access_token = last_access_token
        self.box_request.access_token = last_access_token
        self.tokens_changed = tokens_changed

        if self.access_token == None:
            self.__refresh_access_token()


    def __check_response(self, response, stream=False):
        if stream:
            log_debug('Response from box.com: %s. {Streamed content}' % (response,))
        else:
            log_debug('Response from box.com: %s. %s' %(response, response.text))

        try:
            if stream:
                att = response
            elif response.text is not None and len(response.text) > 0:
                att = response.json()
            else:
                att = {}
        except Exception, ex:
            raise BoxHttpResponseError(ex)

        if response.status_code >= 400:
            raise BoxError(response.status_code, att)
        else:
            return att

    def __refresh_access_token(self):
        log_debug('Access token expired, refreshing it from refresh token')
        resp = self.box_request.refresh_access_token(self.refresh_token)
        self.__log_debug_request(resp)
        att = self.__check_response(resp)
        self.access_token = att['access_token']
        self.refresh_token = att['refresh_token']
        self.box_request.access_token = self.access_token
        if self.tokens_changed:
            self.tokens_changed(self.refresh_token, self.access_token)

    def __request(self, method, command, data=None,
                        querystring=None, files=None, headers=None,
                        stream=None,
                        json_data=True):
        resp = self.box_request.request(method, command,
                                        data, querystring,
                                        files, headers, stream, json_data)

        self.__log_debug_request(resp)

        try:
            att = self.__check_response(resp, stream)
        except BoxError, ex:
            if ex.status != 401:
                raise
            self.__refresh_access_token()
            resp = self.box_request.request(method, command,
                                            data, querystring,
                                            files, headers, stream, json_data)
            self.__log_debug_request(resp)
            att = self.__check_response(resp, stream)

        return att

    def __log_debug_request(self, resp):
        if hasattr(resp.request, 'data'):
            data_req = resp.request.data
        else:
            data_req = ''
        log_debug('Request made to box.com: %s %s\nHEADERS:\n%s\nDATA:\n%s\nBODY:\n%s' %
                    (resp.request.method,
                        resp.request.url,
                        resp.request.headers,
                        data_req,
                        resp.request.body))


    def find_id_in_folder(self, name, parent_folder_id=0):
        """Find a folder or a file ID from its name, inside a given folder.

        Args:
            name (str): Name of the folder or the file to find.

            parent_folder_id (int): ID of the folder where to search.

        Returns:
            int. ID of the file or folder found. None if not found.

        Raises:
            BoxError: An error response is returned from Box (status_code >= 400).

            BoxHttpResponseError: Response from Box is malformed.

            requests.exceptions.*: Any connection related problem.
        """
        if name is None or len(name) == 0:
            return parent_folder_id
        offset = 0
        resp = self.get_folder_items(parent_folder_id,
                                     limit=1000, offset=offset,
                                     fields_list=['name'])
        total = int(resp['total_count'])
        while offset < total:
            found = self.__find_name(resp, name)
            if found is not None:
                return found
            offset += int(len(resp['entries']))
            resp = self.get_folder_items(parent_folder_id,
                                            limit=1000, offset=offset,
                                            fields_list=['name'])

        return None

    def __find_name(self, response, name_to_find):
        for entry in response['entries']:
            if entry['name'] == name_to_find:
                return int(entry['id'])
        return None

    def get_folder_info(self, folder_id):
        """Get info on a folder

        Args:
            folder_id (int): ID of the folder.

        Returns:
            dict. Response from Box.

        Raises:
            BoxError: An error response is returned from Box (status_code >= 400).

            BoxHttpResponseError: Response from Box is malformed.

            requests.exceptions.*: Any connection related problem.
        """
        return self.__request("GET", "folders/%s" % (folder_id, ))

    def create_folder(self, name, parent_folder_id=0):
        """Create a folder

        If the folder exists, a BoxError will be raised.

        Args:
            folder_id (int): Name of the folder.

            parent_folder_id (int): ID of the folder where to create the new one.

        Returns:
            dict. Response from Box.

        Raises:
            BoxError: An error response is returned from Box (status_code >= 400).

            BoxHttpResponseError: Response from Box is malformed.

            requests.exceptions.*: Any connection related problem.
        """
        return self.__request("POST", "folders",
                        data={ "name": name,
                               "parent": {"id": unicode(parent_folder_id)} })

    def delete_folder(self, folder_id, recursive=True):
        """Delete an existing folder

        Args:
            folder_id (int): ID of the folder to delete.
            recursive (bool): Delete all subfolder if True.

        Returns:
            dict. Response from Box.

        Raises:
            BoxError: An error response is returned from Box (status_code >= 400).

            BoxHttpResponseError: Response from Box is malformed.

            requests.exceptions.*: Any connection related problem.
        """
        return self.__request("DELETE", "folders/%s" % (folder_id, ),
                        querystring={'recursive': unicode(recursive).lower()})

    def get_folder_items(self, folder_id,
                            limit=100, offset=0, fields_list=None):
        """Get files and folders inside a given folder

        Args:
            folder_id (int): Where to get files and folders info.

            limit (int): The number of items to return.

            offset (int): The item at which to begin the response.

            fields_list (list): List of attributes to get. All attributes if None.

        Returns:
            dict. Response from Box.

        Raises:
            BoxError: An error response is returned from Box (status_code >= 400).

            BoxHttpResponseError: Response from Box is malformed.

            requests.exceptions.*: Any connection related problem.
        """
        qs = {  "limit": limit,
                "offset": offset }
        if fields_list:
            qs['fields'] = ','.join(fields_list)
        return self.__request("GET", "folders/%s/items" % (folder_id, ),
                        querystring=qs)

    def upload_file(self, name, folder_id, file_path):
        """Upload a file into a folder.

        Use function for small file otherwise there is the chunk_upload_file() function

        Args::
            name (str): Name of the file on your Box storage.

            folder_id (int): ID of the folder where to upload the file.

            file_path (str): Local path of the file to upload.

        Returns:
            dict. Response from Box.

        Raises:
            BoxError: An error response is returned from Box (status_code >= 400).

            BoxHttpResponseError: Response from Box is malformed.

            requests.exceptions.*: Any connection related problem.
        """
        file_obj = open(file_path, 'rb')
        try:
            return self.__request("POST", "files/content",
                                files = {'filename': (name, file_obj)},
                                data = {'parent_id': unicode(folder_id)},
                                json_data = False)
        finally:
            file_obj.close()


    def chunk_upload_file(self, name, folder_id, file_path,
                            progress_callback=None,
                            chunk_size=1024*1024*1):
        """Upload a file chunk by chunk.

        The whole file is never loaded in memory.
        Use this function for big file.

        The callback(transferred, total) to let you know the upload progress.
        Upload can be cancelled if the callback raise an Exception.

        >>> def progress_callback(transferred, total):
        ...    print 'Uploaded %i bytes of %i' % (transferred, total, )
        ...    if user_request_cancel:
        ...       raise MyCustomCancelException()

        Args:
            name (str): Name of the file on your Box storage.

            folder_id (int): ID of the folder where to upload the file.

            file_path (str): Local path of the file to upload.

            progress_callback (func): Function called each time a chunk is uploaded.

            chunk_size (int): Size of chunks.

        Returns:
            dict. Response from Box.

        Raises:
            BoxError: An error response is returned from Box (status_code >= 400).

            BoxHttpResponseError: Response from Box is malformed.

            requests.exceptions.*: Any connection related problem.
        """
        file_obj = open(file_path, 'rb')
        try:
            muw = MultipartUploadWrapper({'parent_id': unicode(folder_id),
                                          'filename': (name, file_obj)},
                                          progress_callback=progress_callback,
                                          chunk_size=chunk_size)
            headers = muw.content_type_header
            return self.__request("POST", "files/content",
                                data = muw,
                                headers = headers,
                                json_data = False)
        finally:
            file_obj.close()


    def get_file_info(self, file_id):
        """Get info on a file

        Args:
            file_id (int): ID of the folder.

        Returns:
            dict. Response from Box.

        Raises:
            BoxError: An error response is returned from Box (status_code >= 400).

            BoxHttpResponseError: Response from Box is malformed.

            requests.exceptions.*: Any connection related problem.
        """
        return self.__request("GET", "files/%s" % (file_id, ))


    def download_file(self, file_id, dest_file_path,
                            progress_callback=None,
                            chunk_size=1024*1024*1):
        """Download a file.

        The whole file is never loaded in memory.

        The callback(transferred, total) to let you know the download progress.
        Download can be cancelled if the callback raise an Exception.

        >>> def progress_callback(transferred, total):
        ...    print 'Downloaded %i bytes of %i' % (transferred, total, )
        ...    if user_request_cancel:
        ...       raise MyCustomCancelException()

        Args:
            file_id (int): ID of the file to download.

            dest_file_path (str): Local path where to store the downloaded filed.

            progress_callback (func): Function called each time a chunk is downloaded.

            chunk_size (int): Size of chunks.

        Raises:
            BoxError: An error response is returned from Box (status_code >= 400).

            BoxHttpResponseError: Response from Box is malformed.

            requests.exceptions.*: Any connection related problem.
        """
        with open(dest_file_path, 'wb') as fp:
            req = self.__request("GET", "files/%s/content" % (file_id, ),
                                                stream=True,
                                                json_data=False)
            total = -1
            if hasattr(req, 'headers'):
                lower_headers = {k.lower():v for k,v in req.headers.items()}
                if 'content-length' in lower_headers:
                    total = lower_headers['content-length']

            transferred = 0
            for chunk in req.iter_content(chunk_size=chunk_size):
                if chunk: # filter out keep-alive new chunks
                    if progress_callback:
                        progress_callback(transferred, total)
                    fp.write(chunk)
                    fp.flush()
                    transferred += len(chunk)

            if progress_callback:
                progress_callback(transferred, total)

    def delete_file(self, file_id):
        """Delete an existing file

        Args:
            file_id (int): ID of the file to delete.

        Returns:
            dict. Response from Box.

        Raises:
            BoxError: An error response is returned from Box (status_code >= 400).

            BoxHttpResponseError: Response from Box is malformed.

            requests.exceptions.*: Any connection related problem.
        """
        return self.__request("DELETE", "files/%s" % (file_id, ))


show_debug_messages = False

def log_debug(message):
    if show_debug_messages == False:
        return
    print '------------------------'
    print message
