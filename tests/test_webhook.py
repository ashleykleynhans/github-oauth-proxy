import pytest
from unittest.mock import patch, MagicMock, mock_open
import json


@pytest.fixture
def app():
    with patch('webhook.load_config', return_value=None):
        import importlib
        import webhook
        importlib.reload(webhook)
        yield webhook.app


@pytest.fixture
def client(app):
    return app.test_client()


class TestGetArgs:
    def test_default_args(self):
        from webhook import get_args
        with patch('sys.argv', ['webhook.py']):
            args = get_args()
            assert args.port == 8090
            assert args.host == '0.0.0.0'

    def test_custom_args(self):
        from webhook import get_args
        with patch('sys.argv', ['webhook.py', '-p', '9000', '-H', '127.0.0.1']):
            args = get_args()
            assert args.port == 9000
            assert args.host == '127.0.0.1'


class TestLoadConfig:
    def test_load_config_file_exists(self):
        from webhook import load_config
        yaml_content = 'github:\n  required:\n    org: MyOrg\n'
        with patch('builtins.open', mock_open(read_data=yaml_content)):
            config = load_config()
            assert config == {'github': {'required': {'org': 'MyOrg'}}}

    def test_load_config_file_not_found(self):
        from webhook import load_config
        with patch('builtins.open', side_effect=FileNotFoundError):
            config = load_config()
            assert config is None

    def test_module_loads_and_validates_config(self):
        import importlib
        import webhook
        yaml_content = 'github:\n  required:\n    org: MyOrg\n'
        with patch('builtins.open', mock_open(read_data=yaml_content)):
            importlib.reload(webhook)
        assert webhook.config == {'github': {'required': {'org': 'MyOrg'}}}


class TestPing:
    def test_ping(self, client):
        response = client.get('/')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'


class TestNotFound:
    def test_404(self, client):
        response = client.get('/nonexistent')
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data['status'] == 'error'


class TestValidateConfig:
    def test_valid_config_with_domain(self):
        from webhook import validate_config
        config = {
            'github': {
                'required': {
                    'email': {
                        'domain': 'example.com',
                        'domain_required_as_primary': True
                    }
                }
            }
        }
        validate_config(config)

    def test_invalid_config_primary_without_domain(self):
        from webhook import validate_config
        config = {
            'github': {
                'required': {
                    'email': {
                        'domain_required_as_primary': True
                    }
                }
            }
        }
        with pytest.raises(KeyError):
            validate_config(config)


class TestValidateOrg:
    def test_valid_org(self):
        from webhook import validate_org
        orgs = [{'login': 'MyOrg'}, {'login': 'OtherOrg'}]
        assert validate_org(orgs, 'MyOrg') is True

    def test_invalid_org(self):
        from webhook import validate_org
        orgs = [{'login': 'OtherOrg'}]
        assert validate_org(orgs, 'MyOrg') is False

    def test_empty_orgs(self):
        from webhook import validate_org
        assert validate_org([], 'MyOrg') is False


class TestValidateEmailDomain:
    def test_matching_domain(self):
        from webhook import validate_email_domain
        emails = [
            {'email': 'user@example.com', 'primary': True},
        ]
        result = validate_email_domain(emails, 'example.com')
        assert result == {
            'email': 'user@example.com',
            'domain': 'example.com',
            'primary': True
        }

    def test_no_matching_domain(self):
        from webhook import validate_email_domain
        emails = [
            {'email': 'user@other.com', 'primary': True},
        ]
        result = validate_email_domain(emails, 'example.com')
        assert result is None

    def test_empty_email_list(self):
        from webhook import validate_email_domain
        assert validate_email_domain([], 'example.com') is None


class TestValidatePrimaryEmail:
    def test_matching_primary(self):
        from webhook import validate_primary_email
        emails = [
            {'email': 'user@example.com', 'primary': True},
        ]
        assert validate_primary_email(emails, 'example.com') is True

    def test_no_matching_primary(self):
        from webhook import validate_primary_email
        emails = [
            {'email': 'user@other.com', 'primary': True},
        ]
        assert validate_primary_email(emails, 'example.com') is False


class TestValidateAuthRequirements:
    def test_valid_org_membership(self):
        from webhook import validate_auth_requirements
        config = {'github': {'required': {'org': 'MyOrg'}}}
        orgs = [{'login': 'MyOrg'}]
        validate_auth_requirements(config, 'testuser', orgs, [])

    def test_invalid_org_membership(self):
        from webhook import validate_auth_requirements
        config = {'github': {'required': {'org': 'MyOrg'}}}
        orgs = [{'login': 'OtherOrg'}]
        with pytest.raises(PermissionError, match='not a member of MyOrg'):
            validate_auth_requirements(config, 'testuser', orgs, [])

    def test_valid_email_domain(self):
        from webhook import validate_auth_requirements
        config = {'github': {'required': {'email': {'domain': 'example.com'}}}}
        emails = [{'email': 'user@example.com', 'primary': True}]
        validate_auth_requirements(config, 'testuser', [], emails)

    def test_invalid_email_domain(self):
        from webhook import validate_auth_requirements
        config = {'github': {'required': {'email': {'domain': 'example.com'}}}}
        emails = [{'email': 'user@other.com', 'primary': False}]
        with pytest.raises(PermissionError, match='does not have a @example.com email'):
            validate_auth_requirements(config, 'testuser', [], emails)

    def test_valid_primary_email(self):
        from webhook import validate_auth_requirements
        config = {'github': {'required': {'email': {
            'domain': 'example.com',
            'domain_required_as_primary': True
        }}}}
        emails = [{'email': 'user@example.com', 'primary': True}]
        validate_auth_requirements(config, 'testuser', [], emails)

    def test_invalid_primary_email(self):
        from webhook import validate_auth_requirements
        config = {'github': {'required': {'email': {
            'domain': 'example.com',
            'domain_required_as_primary': True
        }}}}
        emails = [
            {'email': 'user@example.com', 'primary': True},
            {'email': 'user@other.com', 'primary': True},
        ]
        with patch('webhook.validate_primary_email', return_value=False):
            with pytest.raises(PermissionError, match='does not have an @example.com address'):
                validate_auth_requirements(config, 'testuser', [], emails)


class TestGetUsername:
    def test_returns_mapped_username(self):
        import webhook
        original_config = webhook.config
        webhook.config = {
            'spinnaker': {
                'username_mapping': {
                    'githubuser': 'mappeduser'
                }
            }
        }
        try:
            result = webhook.get_username('githubuser')
            assert result == 'mappeduser'
        finally:
            webhook.config = original_config

    def test_returns_login_when_no_mapping(self):
        import webhook
        original_config = webhook.config
        webhook.config = {}
        try:
            result = webhook.get_username('githubuser')
            assert result == 'githubuser'
        finally:
            webhook.config = original_config


class TestWebhookHandler:
    def test_missing_authorization_header(self, client):
        response = client.get('/info')
        assert response.status_code in [401, 500]

    @patch('webhook.validate_auth_requirements')
    @patch('webhook.GithubAuth')
    def test_successful_request(self, mock_auth_class, mock_validate, client):
        mock_auth = MagicMock()
        mock_auth.get_user_info.return_value = {
            'login': 'testuser',
            'name': 'Test User',
        }
        mock_auth.get_org_list.return_value = [
            {'login': 'MyOrg'}
        ]
        mock_auth.get_email_addresses.return_value = [
            {'email': 'test@example.com', 'primary': True},
        ]
        mock_auth.get_user_teams.return_value = ['backend', 'devops']
        mock_auth_class.return_value = mock_auth

        response = client.get('/info', headers={
            'Authorization': 'Bearer test_token'
        })

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['username'] == 'testuser'
        assert data['firstname'] == 'Test'
        assert data['lastname'] == 'User'
        assert data['email'] == 'test@example.com'
        assert data['roles'] == ['backend', 'devops']
        assert data['orgs'] == 'MyOrg'

    @patch('webhook.GithubAuth')
    def test_permission_error_returns_401(self, mock_auth_class, client):
        mock_auth = MagicMock()
        mock_auth.validate_scopes.side_effect = PermissionError('Missing scopes')
        mock_auth_class.return_value = mock_auth

        response = client.get('/info', headers={
            'Authorization': 'Bearer bad_token'
        })

        assert response.status_code == 401
        data = json.loads(response.data)
        assert data['status'] == 'error'
        assert data['msg'] == 'Unauthorized'

    @patch('webhook.validate_auth_requirements')
    @patch('webhook.GithubAuth')
    def test_empty_teams_when_no_org_config(self, mock_auth_class, mock_validate, client):
        mock_auth = MagicMock()
        mock_auth.get_user_info.return_value = {
            'login': 'testuser',
            'name': 'Test User',
        }
        mock_auth.get_org_list.return_value = []
        mock_auth.get_email_addresses.return_value = [
            {'email': 'test@gmail.com', 'primary': True},
        ]
        mock_auth.get_user_teams.return_value = []
        mock_auth_class.return_value = mock_auth

        response = client.get('/info', headers={
            'Authorization': 'Bearer test_token'
        })

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['roles'] == []


class TestMain:
    @patch('webhook.app')
    @patch('webhook.get_args')
    def test_main_block(self, mock_get_args, mock_app):
        mock_args = MagicMock()
        mock_args.host = '127.0.0.1'
        mock_args.port = 9000
        mock_get_args.return_value = mock_args

        import webhook
        # Read only the __main__ block, padded with newlines to preserve
        # line numbers so coverage tracks lines 219-220
        with open(webhook.__file__) as f:
            lines = f.readlines()
        main_start = next(i for i, l in enumerate(lines) if l.startswith("if __name__"))
        main_source = '\n' * main_start + ''.join(lines[main_start:])
        code = compile(main_source, webhook.__file__, 'exec')
        globs = dict(vars(webhook))
        globs['__name__'] = '__main__'
        exec(code, globs)

        mock_get_args.assert_called_once()
        mock_app.run.assert_called_once_with(host='127.0.0.1', port=9000)
