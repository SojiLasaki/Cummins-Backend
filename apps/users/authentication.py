"""
Optional JWT authentication: invalid or expired tokens are treated as anonymous
instead of returning 401. Views that require auth should use IsAuthenticated.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken, TokenError


class OptionalJWTAuthentication(JWTAuthentication):
    """
    Same as JWTAuthentication but never raises: missing or invalid token
    results in an unauthenticated request (None) so views with AllowAny still work.
    """

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except (InvalidToken, TokenError, AuthenticationFailed):
            return None
