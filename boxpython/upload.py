from mimetools import choose_boundary
from requests.packages.urllib3.filepost import iter_fields
from requests.packages.urllib3.fields import guess_content_type
from io import BytesIO


class MultipartUploadWrapper(object):
    """Adapted from http://stackoverflow.com/questions/15973204/using-python-requests-to-bridge-a-file-without-loading-into-memory
    """

    def __init__(self, files, progress_callback=None, chunk_size=8192):
        """
        Initializer

        :param files:
            A dictionary of files to upload, of the form {'file': ('filename', <file object>)}
        :type network_down_callback:
            Dict
        """
        super(MultipartUploadWrapper, self).__init__()
        self._cursor = 0
        self._body_parts = None
        self._chunk_size = chunk_size
        self._progress_callback = progress_callback
        self._content_length = 0
        self._chunk_transfered = 0
        self.content_type_header = None
        self.content_length_header = None


        self.__create_request_parts(files)

    def __create_request_parts(self, files):
        request_list = []
        boundary = choose_boundary()
        content_length = 0

        boundary_string = b'--%s\r\n' % (boundary)
        for fieldname, value in iter_fields(files):
            content_length += len(boundary_string)

            if isinstance(value, tuple):
                filename, data = value
                content_disposition_string = (('Content-Disposition: form-data; name="%s"; ''filename="%s"\r\n' % (fieldname, filename))
                                            + ('Content-Type: %s\r\n\r\n' % (guess_content_type(filename))))

            else:
                data = value
                content_disposition_string =  (('Content-Disposition: form-data; name="%s"\r\n' % (fieldname))
                                            + 'Content-Type: text/plain\r\n\r\n')
            request_list.append(BytesIO(str(boundary_string + content_disposition_string)))
            content_length += len(content_disposition_string)
            if hasattr(data, 'read'):
                data_stream = data
            else:
                data_stream = BytesIO(str(data))

            data_stream.seek(0,2)
            data_size = data_stream.tell()
            data_stream.seek(0)

            request_list.append(data_stream)
            content_length += data_size

            end_string = b'\r\n'
            request_list.append(BytesIO(end_string))
            content_length += len(end_string)

        request_list.append(BytesIO(b'--%s--\r\n' % (boundary)))
        content_length += len(boundary_string)

        # There's a bug in httplib.py that generates a UnicodeDecodeError on binary uploads if
        # there are *any* unicode strings passed into headers as part of the requests call.
        # For this reason all strings are explicitly converted to non-unicode at this point.
        self.content_type_header = {b'Content-Type': b'multipart/form-data; boundary=%s' % boundary}
        self.content_length_header = {b'Content-Length': str(content_length)}
        self._body_parts = request_list

        self._content_length = content_length + 2


    def __read(self, chunk_size=0):
        remaining_to_read = chunk_size
        output_array = []
        while remaining_to_read > 0:
            body_part = self._body_parts[self._cursor]
            current_piece = body_part.read(remaining_to_read)
            length_read = len(current_piece)
            output_array.append(current_piece)
            if length_read < remaining_to_read:
                # we finished this piece but haven't read enough, moving on to the next one
                remaining_to_read -= length_read
                if self._cursor == len(self._body_parts) - 1:
                    break
                else:
                    self._cursor += 1
            else:
                break
        return b''.join(output_array)

    def __iter__(self):
        return self

    def next(self):
        data = self.__read(self._chunk_size)
        l = len(data)
        if self._progress_callback:
            self._progress_callback(self._chunk_transfered,
                                    self._content_length)

        if l == 0:
            raise StopIteration

        self._chunk_transfered += l
        return data
