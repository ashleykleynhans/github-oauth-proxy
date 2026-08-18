"""GitHub API client used by the oAuth2 proxy.

Wraps the GitHub REST API endpoints needed to validate a user's OAuth
token, scopes, email addresses, organization memberships and team
memberships.
"""

from typing import Any, Dict, List, Mapping, Optional

import requests


class GithubAuth:
    """Authenticated client for the GitHub REST API.

    Attributes:
        required_scopes: OAuth scopes the proxy requires before granting access.
        headers: HTTP headers sent with every request, including the bearer token.
    """

    def __init__(self, access_token: str) -> None:
        """Initialize the client with an OAuth access token.

        Args:
            access_token: The GitHub OAuth access token.

        Raises:
            PermissionError: If ``access_token`` is empty.
        """
        if not access_token:
            raise PermissionError('No access token provided')
        self.required_scopes: List[str] = ['user:email', 'read:org']
        self.headers: Dict[str, str] = {
            'Authorization': f'Bearer {access_token}'
        }

    def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Perform a GET request against the GitHub API.

        Args:
            endpoint: The API path (for example ``/user``).
            params: Optional query string parameters.

        Returns:
            The response, when the request succeeds with HTTP 200.

        Raises:
            PermissionError: If GitHub returns HTTP 401 or 403.
            RuntimeError: If GitHub returns any other non-200 status.
        """
        url = f'https://api.github.com{endpoint}'

        if params:
            r = requests.get(url, headers=self.headers, params=params)
        else:
            r = requests.get(url, headers=self.headers)

        if r.status_code == 200:
            return r

        if r.status_code in (401, 403):
            try:
                message = r.json().get('message', 'unknown error')
            except ValueError:
                message = 'non-JSON response'

            if r.status_code == 401:
                # Authenticating with invalid credentials
                raise PermissionError(f'ERROR: Unauthorized: ({message})')
            # Too many invalid credentials within a short period of time
            raise PermissionError(f'ERROR: Forbidden: ({message})')

        raise RuntimeError(f'ERROR: {r.status_code}')

    def get_headers(self) -> Mapping[str, str]:
        """Return the headers from a request to the GitHub API root.

        Returns:
            The response headers, used to inspect the granted OAuth scopes.

        Raises:
            PermissionError: If GitHub does not return HTTP 200.
        """
        r = requests.get(
            'https://api.github.com',
            headers=self.headers
        )

        if r.status_code != 200:
            raise PermissionError(f'Github returned HTTP status: {r.status_code}')

        return r.headers

    def get_scopes(self) -> List[str]:
        """Return the OAuth scopes granted to the current token.

        Returns:
            A list of granted scope names.

        Raises:
            PermissionError: If the ``X-OAuth-Scopes`` header is missing.
        """
        headers = self.get_headers()

        if 'X-OAuth-Scopes' not in headers:
            raise PermissionError('X-OAuth-Scopes header not found in Github response')

        scopes = headers['X-OAuth-Scopes']
        scopes = scopes.replace(' ', '')
        return scopes.split(',')

    def validate_scopes(self) -> None:
        """Ensure the token grants every required OAuth scope.

        Raises:
            PermissionError: If one or more required scopes are missing.
        """
        missing_scopes = []
        granted_scopes = self.get_scopes()

        for required_scope in self.required_scopes:
            if required_scope not in granted_scopes:
                missing_scopes.append(required_scope)

        if missing_scopes:
            separator = "' or '"
            raise PermissionError(
                f"Token does not have permission for '{separator.join(missing_scopes)}' scope(s)"
            )

    def call_github_api_endpoint(self, endpoint: str) -> Any:
        """Return the JSON payload from a GitHub API endpoint.

        Args:
            endpoint: The API path (for example ``/user/emails``).

        Returns:
            The decoded JSON response body.

        Raises:
            PermissionError: If GitHub returns HTTP 401 or 403.
            RuntimeError: If GitHub returns any other non-200 status.
        """
        r = self._request(endpoint)
        return r.json()

    def get_email_addresses(self) -> Any:
        """Return the email addresses associated with the account.

        Returns:
            The decoded ``/user/emails`` response.
        """
        return self.call_github_api_endpoint('/user/emails')

    def get_org_list(self) -> Any:
        """Return the organizations the authenticated user belongs to.

        Returns:
            The decoded ``/user/orgs`` response.
        """
        return self.call_github_api_endpoint('/user/orgs')

    def get_user_info(self) -> Any:
        """Return the authenticated user's profile.

        Returns:
            The decoded ``/user`` response.
        """
        return self.call_github_api_endpoint('/user')

    def get_user_teams(self, config: Optional[Dict[str, Any]]) -> List[str]:
        """Return team slugs for the configured GitHub organization.

        Only teams belonging to ``github.required.org`` in the configuration
        are returned. If no organization is configured, an empty list is
        returned without contacting GitHub.

        Note:
            ``/user/teams`` is deprecated by GitHub but remains the only REST
            endpoint that lists the authenticated user's team memberships.
            The org-scoped ``/orgs/{org}/teams`` endpoint would return every
            team visible to the user and therefore over-grant roles.

        Args:
            config: The loaded configuration, or ``None``.

        Returns:
            The team slugs the user belongs to in the required organization.

        Raises:
            PermissionError: If GitHub returns HTTP 401 or 403.
            RuntimeError: If GitHub returns any other non-200 status.
        """
        teams: List[str] = []

        if not config \
                or 'github' not in config \
                or 'required' not in config['github'] \
                or 'org' not in config['github']['required']:
            return teams

        org = config['github']['required']['org']
        page = 1

        while True:
            r = self._request('/user/teams', params={'page': page, 'per_page': 100})
            page_teams = r.json()

            if not page_teams:
                break

            for team in page_teams:
                org_login = (team.get('organization') or {}).get('login', '')
                if org_login.lower() == org.lower():
                    teams.append(team.get('slug'))

            page += 1

        return teams
