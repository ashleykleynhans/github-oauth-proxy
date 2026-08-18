#!/usr/bin/env python3
"""GitHub oAuth2 proxy for Spinnaker.

Exposes a Flask application that validates GitHub OAuth tokens and returns
a Spinnaker-compatible user profile, optionally enforcing organization,
email-domain and primary-email requirements from ``config.yml``.
"""

import argparse
from typing import Any, Dict, List, Optional

import yaml
from flask import Flask, request, jsonify, make_response

from github_auth import GithubAuth


def get_args() -> argparse.Namespace:
    """Parse command-line arguments for the local development server.

    Returns:
        The parsed arguments (``host`` and ``port``).
    """
    parser = argparse.ArgumentParser(
        description='Github Webhook proxy for Jenkins'
    )

    parser.add_argument(
        '-p', '--port',
        help='Port to listen on',
        type=int,
        default=8090
    )

    parser.add_argument(
        '-H', '--host',
        help='Host to bind to',
        default='0.0.0.0'
    )

    return parser.parse_args()


def load_config() -> Optional[Dict[str, Any]]:
    """Load ``config.yml`` from the current directory.

    Returns:
        The parsed configuration, or ``None`` if the file does not exist.
    """
    try:
        with open('config.yml', 'r') as stream:
            return yaml.safe_load(stream)
    except FileNotFoundError:
        return None


def validate_config(config: Dict[str, Any]) -> None:
    """Validate the loaded configuration.

    Args:
        config: The parsed configuration.

    Raises:
        KeyError: If ``domain_required_as_primary`` is set without a domain.
    """
    if 'github' in config and 'required' in config['github']:
        required = config['github']['required']
        if 'email' in required and 'domain_required_as_primary' in required['email']:
            if 'domain' not in required['email']:
                raise KeyError('Configuration requires a specific domain name as a ' +
                               'primary email, but no domain was provided')


def validate_org(orgs: List[Dict[str, Any]], required_org: str) -> bool:
    """Return whether the user belongs to the required organization.

    Args:
        orgs: The list of organizations from GitHub.
        required_org: The required organization login.

    Returns:
        ``True`` if the required organization is present (case-insensitive).
    """
    for org in orgs:
        if org.get('login', '').lower() == required_org.lower():
            return True
    return False


def validate_email_domain(
    email_list: List[Dict[str, Any]],
    required_domain: str,
) -> Optional[Dict[str, Any]]:
    """Return the first email matching the required domain.

    Args:
        email_list: The list of email entries from GitHub.
        required_domain: The required email domain.

    Returns:
        A dict describing the matching email, or ``None`` when there is no match.
    """
    for email_item in email_list:
        email_address = email_item.get('email') or ''
        email_domain = email_address.partition('@')[2].lower()
        if email_domain and email_domain == required_domain.lower():
            return {
                'email': email_address,
                'domain': email_domain,
                'primary': email_item.get('primary')
            }
    return None


def validate_primary_email(
    email_list: List[Dict[str, Any]],
    required_email_domain: str,
) -> bool:
    """Return whether a primary email matches the required domain.

    Args:
        email_list: The list of email entries from GitHub.
        required_email_domain: The required email domain.

    Returns:
        ``True`` if a primary email with the required domain exists.
    """
    for email_item in email_list:
        email_address = email_item.get('email') or ''
        email_domain = email_address.partition('@')[2].lower()
        if email_item.get('primary') and email_domain == required_email_domain.lower():
            return True
    return False


def validate_auth_requirements(
    config: Optional[Dict[str, Any]],
    username: str,
    orgs: List[Dict[str, Any]],
    emails: List[Dict[str, Any]],
) -> None:
    """Enforce the configured organization and email requirements.

    Args:
        config: The loaded configuration, or ``None``.
        username: The GitHub login of the authenticated user.
        orgs: The list of organizations from GitHub.
        emails: The list of email entries from GitHub.

    Raises:
        PermissionError: If any configured requirement is not satisfied.
    """
    required: Dict[str, Any] = {}
    if config and 'github' in config and 'required' in config['github']:
        required = config['github']['required']

    if 'org' in required:
        required_org = required['org']
        if not validate_org(orgs, required_org):
            raise PermissionError(f'User {username} is not a member of {required_org} Github organization')

    if 'email' in required and 'domain' in required['email']:
        domain = required['email']['domain']
        validated_email = validate_email_domain(emails, domain)
        if not validated_email:
            raise PermissionError(f'User {username} does not have a @{domain} email ' +
                                  'address associated with their Github account')

        if required['email'].get('domain_required_as_primary'):
            if not validate_primary_email(emails, domain):
                raise PermissionError(f'User {username} does not have an @{domain} address ' +
                                      'set as their primary email address')


def get_username(login: str) -> str:
    """Map a GitHub login to the configured Spinnaker username.

    Args:
        login: The GitHub login.

    Returns:
        The mapped username if a mapping exists, otherwise ``login``.
    """
    if config \
            and 'spinnaker' in config \
            and 'username_mapping' in config['spinnaker'] \
            and login in config['spinnaker']['username_mapping']:
        return config['spinnaker']['username_mapping'][login]
    else:
        return login


app = Flask(__name__)
config: Optional[Dict[str, Any]] = load_config()

if config:
    validate_config(config)


@app.errorhandler(404)
def not_found(error):
    """Return a JSON 404 response for unknown routes."""
    return make_response(jsonify(
        {
            'status': 'error',
            'msg': f'{request.url} not found'
        }
    ), 404)


@app.errorhandler(500)
def internal_server_error(error):
    """Log an unhandled exception and return a JSON 500 response."""
    app.logger.exception('Unhandled exception: %s', error)
    return make_response(jsonify(
        {
            'status': 'error',
            'msg': 'Internal Server Error'
        }
    ), 500)


@app.route('/')
def ping():
    """Return a health-check response."""
    return make_response(jsonify(
        {
            'status': 'ok'
        }
    ), 200)


@app.route('/info', methods=['GET'])
def webhook_handler():
    """Handle the ``/info`` endpoint for Spinnaker's user info URI.

    Validates the bearer token, gathers the user profile, enforces any
    configured requirements, and returns the fields Spinnaker expects.
    """
    try:
        headers = request.headers

        if 'Authorization' not in headers:
            return make_response(jsonify(
                {
                    'status': 'error',
                    'msg': 'Authorization header not found in request'
                }
            ), 401)

        auth_header = headers.get('Authorization')

        if not auth_header:
            return make_response(jsonify(
                {
                    'status': 'error',
                    'msg': 'Authorization header not present or empty'
                }
            ), 401)

        auth = auth_header.split(' ')
        access_token = auth[-1]
        github = GithubAuth(access_token)
        github.validate_scopes()
        info = github.get_user_info()
        orgs = github.get_org_list()
        emails = github.get_email_addresses()
        teams = github.get_user_teams(config)
        validate_auth_requirements(config, info['login'], orgs, emails)

        name = (info.get('name') or '').strip()
        name_parts = name.split()
        firstname = name_parts[0] if name_parts else ''
        lastname = name_parts[-1] if len(name_parts) > 1 else ''

        primary_email = ''
        org_list = []

        for email in emails:
            if email.get('primary'):
                primary_email = email.get('email', '')

        for org in orgs:
            org_list.append(org.get('login', ''))

        org_memberships = ','.join(org_list)

        user_info = {
            'username': get_username(info['login']),
            'firstname': firstname,
            'lastname': lastname,
            'email': primary_email,
            'roles': ','.join(teams),
            # You could use a regex to check this, but it can possibly match
            # orgs with similar names instead of doing exact matching
            'orgs': org_memberships,
            # This should actually be checked by Gate but is not
            'organizations_url': 'https://api.github.com/user/orgs',
        }

        return make_response(jsonify(user_info), 200)
    except PermissionError as e:
        app.logger.warning('Authorization failed: %s', e)
        return make_response(jsonify(
            {
                'status': 'error',
                'msg': 'Unauthorized',
                'detail': str(e)
            }
        ), 401)


if __name__ == '__main__':
    args = get_args()
    # Deferred import: waitress is only needed for the standalone server;
    # Zappa/API Gateway serves the app in AWS Lambda, so importing it here
    # keeps the module importable without a hard waitress dependency.
    from waitress import serve
    serve(app, host=args.host, port=args.port)
