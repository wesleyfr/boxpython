
class BoxHttpResponseError(Exception):
    pass

class BoxError(Exception):
    def __init__(self, status, attributes):
        self.status = status
        self.code = None
        self.help_url = None
        self.message = None
        self.request_id = None
        self.error = None
        self.error_description = None

        for (key, value) in attributes.iteritems():
            if key in self.__dict__:
                self.__dict__[key] = value

        msg_err = ''
        if self.message is not None:
            msg_err += self.message + '. '

        if self.error is not None:
            msg_err += self.error + '. '

        if self.error_description is not None:
            msg_err += self.error_description + '. '

        super(BoxError, self).__init__( '%s - %s' %
                                        (self.status, msg_err))
