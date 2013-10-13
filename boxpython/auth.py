from .request import BoxRestRequest
from .exceptions import BoxError, BoxHttpResponseError


class BoxAuthenticateFlow(object):
    """From the Client ID and Client Secret from Box, get the Access Token and the Refresh Token.

    Usage:
        >>> flow = BoxAuthenticateFlow('my_id', 'my_secret')
        >>> url = flow.get_authorization_url()
        ...
        ...
        >>> access_token, refresh_token = flow.get_access_tokens('generated_auth_code')

    """
    def __init__(self, client_id, client_secret):
        """Constructor

        Args:
            client_id (str): Client ID provided by Box.

            client_secret (str): Client Secret provided by Box.
        """
        self.box_request = BoxRestRequest(client_id, client_secret)
        self.client_id = client_id
        self.client_secret = client_secret

    def get_authorization_url(self, redirect_uri=None):
        """Get the url used to get an authorization code.

        Args:
            redirect_uri (str): Https url where Box will redirect the user with the authorization code in the querystring. If None the value stored in the Box application settings will be used.

        Returns:
            str. Url used to get an authorization code.
        """
        return self.box_request.get_authorization_url(redirect_uri)

    def get_access_tokens(self, authorization_code):
        """From the authorization code, get the "access token" and the "refresh token" from Box.

        Args:
            authorization_code (str). Authorisation code emitted by Box at the url provided by the function :func:`get_authorization_url`.

        Returns:
            tuple. (access_token, refresh_token)

        Raises:
            BoxError: An error response is returned from Box (status_code >= 400).

            BoxHttpResponseError: Response from Box is malformed.

            requests.exceptions.*: Any connection related problem.
        """
        response = self.box_request.get_access_token(authorization_code)
        try:
            att = response.json()
        except Exception, ex:
            raise BoxHttpResponseError(ex)

        if response.status_code >= 400:
            raise BoxError(response.status_code, att)

        return att['access_token'], att['refresh_token']

