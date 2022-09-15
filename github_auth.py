import requests


class GithubAuth(object):
    def __init__(self, access_token):
        self. required_scopes = ['user:email', 'read:org']
        self.headers = {
            'Authorization': f'Bearer {access_token}'
        }

    def get_headers(self):
        r = requests.get(
            'https://api.github.com',
            headers=self.headers
        )

        return r.headers

    def get_scopes(self):
        headers = self.get_headers()
        scopes = headers['X-OAuth-Scopes']
        scopes = scopes.replace(' ', '')
        return scopes.split(',')

    def validate_scopes(self):
        missing_scopes = []
        granted_scopes = self.get_scopes()

        for required_scope in self.required_scopes:
            if required_scope not in granted_scopes:
                missing_scopes.append(required_scope)

        if len(missing_scopes):
            separator = "' or '"
            raise PermissionError(f"Token does not have permission for '{separator.join(missing_scopes)}' scope(s)")

    def call_github_api_endpoint(self, endpoint):
        r = requests.get(
            f'https://api.github.com{endpoint}',
            headers=self.headers
        )

        data = r.json()

        if r.status_code == 200:
            return data
        elif r.status_code == 401:
            # Authenticating with invalid credentials
            raise PermissionError(f'ERROR: Unauthorized: ({data["message"]})')
        elif r.status_code == 403:
            # Too many invalid credentials within a short period of time
            raise PermissionError(f'ERROR: Forbidden: ({data["message"]})')
        else:
            raise Exception(f'ERROR: {r.status_code}')

    def get_email_addresses(self):
        return self.call_github_api_endpoint('/user/emails')

    def get_org_list(self):
        return self.call_github_api_endpoint('/user/orgs')

    def get_user_info(self):
        return self.call_github_api_endpoint('/user')
