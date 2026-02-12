import pytest
from unittest.mock import patch, MagicMock
from github_auth import GithubAuth


class TestGithubAuthInit:
    def test_init_with_valid_token(self):
        auth = GithubAuth('valid_token')
        assert auth.headers == {'Authorization': 'Bearer valid_token'}

    def test_init_with_empty_token(self):
        with pytest.raises(PermissionError, match='No access token provided'):
            GithubAuth('')

    def test_init_with_none_token(self):
        with pytest.raises(PermissionError, match='No access token provided'):
            GithubAuth(None)


class TestGetHeaders:
    @patch('github_auth.requests.get')
    def test_get_headers_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'X-OAuth-Scopes': 'user:email, read:org'}
        mock_get.return_value = mock_response

        auth = GithubAuth('token')
        headers = auth.get_headers()
        assert headers == {'X-OAuth-Scopes': 'user:email, read:org'}
        mock_get.assert_called_once_with(
            'https://api.github.com',
            headers={'Authorization': 'Bearer token'}
        )

    @patch('github_auth.requests.get')
    def test_get_headers_non_200(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        auth = GithubAuth('token')
        with pytest.raises(PermissionError, match='Github returned HTTP status: 500'):
            auth.get_headers()


class TestGetScopes:
    @patch('github_auth.requests.get')
    def test_get_scopes_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'X-OAuth-Scopes': 'user:email, read:org'}
        mock_get.return_value = mock_response

        auth = GithubAuth('token')
        scopes = auth.get_scopes()
        assert scopes == ['user:email', 'read:org']

    @patch('github_auth.requests.get')
    def test_get_scopes_missing_header(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_get.return_value = mock_response

        auth = GithubAuth('token')
        with pytest.raises(PermissionError, match='X-OAuth-Scopes header not found'):
            auth.get_scopes()


class TestValidateScopes:
    @patch('github_auth.requests.get')
    def test_validate_scopes_all_present(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'X-OAuth-Scopes': 'user:email, read:org'}
        mock_get.return_value = mock_response

        auth = GithubAuth('token')
        auth.validate_scopes()

    @patch('github_auth.requests.get')
    def test_validate_scopes_missing_scope(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'X-OAuth-Scopes': 'user:email'}
        mock_get.return_value = mock_response

        auth = GithubAuth('token')
        with pytest.raises(PermissionError, match="read:org"):
            auth.validate_scopes()

    @patch('github_auth.requests.get')
    def test_validate_scopes_all_missing(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'X-OAuth-Scopes': 'repo'}
        mock_get.return_value = mock_response

        auth = GithubAuth('token')
        with pytest.raises(PermissionError, match="user:email.+read:org"):
            auth.validate_scopes()


class TestCallGithubApiEndpoint:
    @patch('github_auth.requests.get')
    def test_call_endpoint_200(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'login': 'testuser'}
        mock_get.return_value = mock_response

        auth = GithubAuth('token')
        result = auth.call_github_api_endpoint('/user')
        assert result == {'login': 'testuser'}
        mock_get.assert_called_once_with(
            'https://api.github.com/user',
            headers={'Authorization': 'Bearer token'}
        )

    @patch('github_auth.requests.get')
    def test_call_endpoint_401(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {'message': 'Bad credentials'}
        mock_get.return_value = mock_response

        auth = GithubAuth('token')
        with pytest.raises(PermissionError, match='Unauthorized.*Bad credentials'):
            auth.call_github_api_endpoint('/user')

    @patch('github_auth.requests.get')
    def test_call_endpoint_403(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {'message': 'Rate limit exceeded'}
        mock_get.return_value = mock_response

        auth = GithubAuth('token')
        with pytest.raises(PermissionError, match='Forbidden.*Rate limit exceeded'):
            auth.call_github_api_endpoint('/user')

    @patch('github_auth.requests.get')
    def test_call_endpoint_other_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.json.return_value = {}
        mock_get.return_value = mock_response

        auth = GithubAuth('token')
        with pytest.raises(Exception, match='ERROR: 502'):
            auth.call_github_api_endpoint('/user')


class TestApiEndpointWrappers:
    @patch.object(GithubAuth, 'call_github_api_endpoint')
    def test_get_email_addresses(self, mock_call):
        mock_call.return_value = [{'email': 'test@example.com'}]
        auth = GithubAuth('token')
        result = auth.get_email_addresses()
        mock_call.assert_called_once_with('/user/emails')
        assert result == [{'email': 'test@example.com'}]

    @patch.object(GithubAuth, 'call_github_api_endpoint')
    def test_get_org_list(self, mock_call):
        mock_call.return_value = [{'login': 'myorg'}]
        auth = GithubAuth('token')
        result = auth.get_org_list()
        mock_call.assert_called_once_with('/user/orgs')
        assert result == [{'login': 'myorg'}]

    @patch.object(GithubAuth, 'call_github_api_endpoint')
    def test_get_user_info(self, mock_call):
        mock_call.return_value = {'login': 'testuser'}
        auth = GithubAuth('token')
        result = auth.get_user_info()
        mock_call.assert_called_once_with('/user')
        assert result == {'login': 'testuser'}


class TestGetUserTeams:
    @patch('github_auth.requests.get')
    def test_returns_empty_list_when_no_config(self, mock_get):
        auth = GithubAuth('token')
        assert auth.get_user_teams(None) == []

    @patch('github_auth.requests.get')
    def test_returns_empty_list_when_no_github_key(self, mock_get):
        auth = GithubAuth('token')
        assert auth.get_user_teams({}) == []

    @patch('github_auth.requests.get')
    def test_returns_empty_list_when_no_required_key(self, mock_get):
        auth = GithubAuth('token')
        assert auth.get_user_teams({'github': {}}) == []

    @patch('github_auth.requests.get')
    def test_returns_empty_list_when_no_org_key(self, mock_get):
        auth = GithubAuth('token')
        assert auth.get_user_teams({'github': {'required': {}}}) == []

    @patch('github_auth.requests.get')
    def test_returns_teams_for_matching_org(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {'slug': 'backend', 'organization': {'login': 'MyOrg'}},
            {'slug': 'frontend', 'organization': {'login': 'OtherOrg'}},
            {'slug': 'devops', 'organization': {'login': 'myorg'}},
        ]
        mock_empty = MagicMock()
        mock_empty.status_code = 200
        mock_empty.json.return_value = []
        mock_get.side_effect = [mock_response, mock_empty]

        config = {'github': {'required': {'org': 'MyOrg'}}}
        auth = GithubAuth('token')
        teams = auth.get_user_teams(config)
        assert teams == ['backend', 'devops']

    @patch('github_auth.requests.get')
    def test_handles_pagination(self, mock_get):
        page1 = MagicMock()
        page1.status_code = 200
        page1.json.return_value = [
            {'slug': 'team1', 'organization': {'login': 'MyOrg'}},
        ]
        page2 = MagicMock()
        page2.status_code = 200
        page2.json.return_value = [
            {'slug': 'team2', 'organization': {'login': 'MyOrg'}},
        ]
        page3 = MagicMock()
        page3.status_code = 200
        page3.json.return_value = []
        mock_get.side_effect = [page1, page2, page3]

        config = {'github': {'required': {'org': 'MyOrg'}}}
        auth = GithubAuth('token')
        teams = auth.get_user_teams(config)
        assert teams == ['team1', 'team2']

    @patch('github_auth.requests.get')
    def test_stops_on_non_200(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        config = {'github': {'required': {'org': 'MyOrg'}}}
        auth = GithubAuth('token')
        teams = auth.get_user_teams(config)
        assert teams == []
